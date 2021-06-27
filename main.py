import atexit
import json
import logging
import typing as tp
from time import sleep

import requests
from flask import Flask, request, Response
from flask_restful import Api, Resource

import Views
from Display import Display
from Employee import Employee
from Spoke import Spoke

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    # filename="spoke-daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s",
)

spoke = Spoke()  # initialize Spoke object
worker = Employee()  # create Employee object
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
        event_dict: tp.Dict[str, tp.Any] = request.get_json()  # type: ignore
        logging.debug(f"Received event dict:\n{event_dict}")

        # handle the event in accord with it's source
        sender = spoke.identify_sender(event_dict["name"])

        if sender == "rfid_reader":
            self._handle_rfid_event(event_dict)
        elif sender == "barcode_reader":
            self._handle_barcode_event(event_dict)
        else:
            logging.error(
                "Sender of the event dict is not mentioned in the config. Can't handle the request."
            )

    @staticmethod
    def _handle_barcode_event(event_dict: tp.Dict[str, tp.Any]) -> None:
        # ignore the event if unauthorized
        if not worker.is_authorized:
            logging.info(f"Ignoring barcode event: worker not authorized.")
            display.render_view(Views.AuthorizeFirstScreen)
            sleep(3)
            display.render_view(Views.LoginScreen)
            return

        # make a request to the hub regarding the barcode
        barcode_string = event_dict["string"]
        logging.info(f"Making a request to hub regarding the barcode {barcode_string}")

        try:
            if spoke.config["developer"]["disable_barcode_validation"]:  # skip barcode validation
                response_data = {"status": True}

            else:
                if spoke.recording_in_progress:
                    url = f"{spoke.hub_url}/api/unit/{barcode_string}/start"
                    payload = {
                        "workbench_no": spoke.number,
                        "production_stage_name": spoke.config["general"]["production_stage_name"],
                        "additional_info": {},
                    }

                    spoke.associated_unit_internal_id = barcode_string

                else:
                    url = f"{spoke.hub_url}/api/unit/{barcode_string}/end"
                    payload = {"workbench_no": spoke.number, "additional_info": {}}

                    spoke.associated_unit_internal_id = ""

                response = requests.post(url=url, json=payload)
                response_data = response.json()

            if response_data["status"]:
                # end ongoing operation if there is one
                if spoke.recording_in_progress:
                    # switch back to await screen
                    logging.debug("Recording in progress. Stopping.")
                    display.render_view(Views.AwaitInputScreen)

                else:
                    # switch to ongoing operation screen since validation succeeded
                    logging.debug("Starting recording.")
                    display.render_view(Views.OngoingOperationScreen)

                spoke.invert_rec_flag()
            else:
                logging.error(
                    f"Barcode validation failed: hub returned '{response_data['comment']}'"
                )

        except Exception as E:
            logging.error(f"Request to the hub failed:\n{E}")

    @staticmethod
    def _handle_rfid_event(event_dict: tp.Dict[str, tp.Any]) -> None:
        # if worker is logged in - log him out
        if worker.is_authorized:
            spoke.end_recording()
            worker.log_out()

            payload = {"workbench_no": spoke.number}
            url = f"{spoke.hub_url}/api/employee/log-out"
            requests.post(url=url, json=payload)

            display.render_view(Views.LoginScreen)
            return

        # perform development log in if set in config
        if spoke.config["developer"]["disable_id_validation"]:
            logging.info("Employee authorized regardless of the ID card: development auth is on.")
            worker.log_in("Младший инженер", "Иванов Иван Иванович")

        else:
            # make a call to authorize the worker otherwise
            try:
                payload = {
                    "workbench_no": spoke.number,
                    "employee_rfid_card_no": event_dict["string"],
                }
                url = f"{spoke.hub_url}/api/employee/log-in"
                response = requests.post(url=url, json=payload)
                response_data = response.json()

                # check if worker authorized and log him in
                if response_data["status"]:
                    name = response_data["employee_data"]["name"]
                    position = response_data["employee_data"]["position"]
                    worker.log_in(position, name)
                else:
                    logging.error("Employee could not be authorized: hub rejected ID card")

            except Exception as E:
                logging.error(f"An error occurred while logging the worker in:\n{E}")

        if worker.is_authorized:
            display.render_view(Views.SuccessfulAuthorizationScreen)
            sleep(3)
            display.render_view(Views.AwaitInputScreen)
        else:
            display.render_view(Views.FailedAuthorizationScreen)
            sleep(3)
            display.render_view(Views.LoginScreen)


class ResetState(Resource):
    """resets Spoke state back to 0 in case of a corresponding POST request"""

    @staticmethod
    def post() -> Response:
        display.render_view(Views.LoginScreen)
        message = {"message": "Successful state transition back to 0"}
        payload = json.dumps(message)
        return Response(response=payload, status=200)


# REST API endpoints
api.add_resource(HidEventHandler, "/api/hid_event")
api.add_resource(ResetState, "/api/reset_state")

# entry point
if __name__ == "__main__":
    display.render_view(Views.LoginScreen)
    app.run(  # start the server
        host=spoke.config["api"]["server_ip"], port=spoke.config["api"]["server_port"]
    )
