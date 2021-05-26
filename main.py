from Display import Display
import atexit
import threading
import logging
import funcs
import requests
import typing as tp
from flask import Flask, request
from flask_restful import Api, Resource
from Worker import Worker

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    # filename="spoke-daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)

config: tp.Dict[str, tp.Dict[str, tp.Any]] = funcs.read_configuration("config.yaml")  # parse configuration
worker = Worker()  # create Worker object
display: Display = Display(config, worker)  # instantiate Display
display_thread: threading.Thread = threading.Thread(target=display.run)  # make a thread for the display to run in
app = Flask(__name__)  # create a Flask app
api = Api(app)  # create a Flask API


@atexit.register  # define the behaviour when the script execution is completed
def end_session() -> None:
    """clear the display, release SPI and join the thread before exiting"""

    display.end_session()
    display_thread.join(timeout=1)


class HidEventHandler(Resource):
    """handles RFID and barcode scanner events"""

    def post(self) -> None:
        # parse the event dict JSON
        event_dict: dict = request.get_json()
        logging.debug(f"Received event dict:\n{event_dict}")

        # identify, from which device the input is coming from
        known_hid_devices: tp.Dict[str, str] = config["known_hid_devices"]
        sender = ""  # name of the sender device

        for sender_name, device_name in known_hid_devices.items():
            if device_name == event_dict["name"]:
                sender = sender_name
                break

        if not sender:
            logging.error("Sender of the event dict is not mentioned in the config. Can't handle the request.")
            return

        global worker, display

        # handle the event in accord with it's source
        if sender == "rfid_reader":
            # if worker is logged in - log him out
            if worker.is_authorized:
                worker.log_out()
                display.state = 0
                return

            # make a call to authorize the worker otherwise
            try:
                response = requests.post(
                    url=f'{config["endpoints"]["hub_socket"]}/api/validator',
                    json={"rfid_string": event_dict["string"]}
                )

                response = response.json()

                # check if worker authorized and log him in
                if response["is_valid"]:
                    worker.full_name = response["employee_name"]
                    worker.position = response["position"]
                    worker.log_in()
                else:
                    logging.error("Worker could not be authorized: hub rejected ID card")

            except Exception as E:
                logging.error(f"An error occurred while logging the worker in:\n{E}")

            # development log in
            if config["developer"]["disable_id_validation"]:
                logging.info("Worker authorized regardless of the ID card: development auth is on.")
                worker.full_name = "Иванов Иван Иванович"
                worker.position = "Младший инженер"
                worker.log_in()

            display.state = 1

        # todo
        elif sender == "barcode_reader":
            # ignore the event if unauthorized
            if not worker.is_authorized:
                logging.info(f"Ignoring barcode event: worker not authorized.")
                return

            # make a request to the hub regarding the ID
            barcode_string = event_dict["string"]


class ResetState(Resource):
    """resets Spoke state back to 0 in case of a corresponding POST request"""

    def post(self) -> dict:
        display.state = 0

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
    display_thread.start()  # start the display daemon
    app.run(  # start the server
        host=config["api"]["server_ip"],
        port=config["api"]["server_port"]
    )
