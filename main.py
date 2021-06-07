import atexit
import logging
import typing as tp

from flask import Flask, request
from flask_restful import Api, Resource

from Display import Display
from Spoke import Spoke
from Views import LoginScreen, AwaitInputScreen, OngoingOperationScreen, AuthorizationScreen
from Worker import Worker

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    # filename="spoke-daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)

spoke = Spoke()  # initialize Spoke object
worker = Worker()  # create Worker object
display: Display = Display(worker, spoke)  # instantiate Display
app = Flask(__name__)  # create a Flask app
api = Api(app)  # create a Flask API


@atexit.register  # define the behaviour when the script execution is completed
def end_session() -> None:
    """clear the display, release SPI and join the thread before exiting"""

    display.end_session()


class HidEventHandler(Resource):
    """handles RFID and barcode scanner events"""

    def post(self) -> None:
        # parse the event dict JSON
        event_dict: tp.Dict[str, tp.Any] = request.get_json()
        logging.debug(f"Received event dict:\n{event_dict}")

        # handle the event in accord with it's source
        sender = spoke.identify_sender(event_dict["name"])

        if sender == "rfid_reader":
            self._handle_rfid_event(event_dict)
        elif sender == "barcode_reader":
            self._handle_barcode_event(event_dict)
        else:
            logging.error("Sender of the event dict is not mentioned in the config. Can't handle the request.")

    @staticmethod
    def _handle_barcode_event(event_dict: tp.Dict[str, tp.Any]) -> None:
        # ignore the event if unauthorized
        if not worker.is_authorized:
            logging.info(f"Ignoring barcode event: worker not authorized.")
            return

        # make a request to the hub regarding the barcode
        barcode_string = event_dict["string"]
        logging.info(f"Making a request to hub regarding the barcode {barcode_string}")

        payload = {
            "barcode_string": barcode_string,
            "employee_name": worker.full_name,
            "position": worker.position,
            "spoke_num": spoke.config["general"]["spoke_num"]
        }

        try:
            if spoke.config["developer"]["disable_barcode_validation"]:  # skip barcode validation
                response_data = {"status": True}
            else:
                response_data = spoke.submit_barcode(payload)  # perform barcode validation otherwise

            if response_data["status"]:
                # end ongoing operation if there is one
                if spoke.recording_in_progress:
                    # switch back to await screen
                    display.render_view(AwaitInputScreen)

                else:
                    # switch to ongoing operation screen since validation succeeded
                    display.render_view(OngoingOperationScreen)
            else:
                logging.error(f"Barcode validation failed: hub returned '{response_data['comment']}'")

        except Exception as E:
            logging.error(f"Request to the hub failed:\n{E}")

    @staticmethod
    def _handle_rfid_event(event_dict: tp.Dict[str, tp.Any]) -> None:
        # if worker is logged in - log him out
        if worker.is_authorized:
            spoke.end_recording()
            worker.log_out()
            display.render_view(LoginScreen)
            return

        # perform development log in if set in config
        if spoke.config["developer"]["disable_id_validation"]:
            logging.info("Worker authorized regardless of the ID card: development auth is on.")
            worker.log_in("Младший инженер", "Иванов Иван Иванович")

        else:
            # make a call to authorize the worker otherwise
            try:
                payload = {"rfid_string": event_dict["string"]}
                response_data = spoke.submit_rfid(payload)

                # check if worker authorized and log him in
                if response_data["is_valid"]:
                    worker.log_in(response_data["position"], response_data["employee_name"])
                else:
                    logging.error("Worker could not be authorized: hub rejected ID card")

            except Exception as E:
                logging.error(f"An error occurred while logging the worker in:\n{E}")

        display.render_view(AuthorizationScreen)


class ResetState(Resource):
    """resets Spoke state back to 0 in case of a corresponding POST request"""

    @staticmethod
    def post() -> tp.Dict[str, tp.Any]:
        display.render_view(LoginScreen)

        message = {
            "status": 200,
            "message": "Successful state transition back to 0"
        }

        return message


# REST API endpoints
api.add_resource(HidEventHandler, "/api/hid_event")
api.add_resource(ResetState, "/api/reset_state")

# entry point
if __name__ == "__main__":
    display.render_view(LoginScreen)
    app.run(  # start the server
        host=spoke.config["api"]["server_ip"],
        port=spoke.config["api"]["server_port"]
    )
