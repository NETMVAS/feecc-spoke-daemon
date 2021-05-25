from Display import Display
import atexit
from time import sleep
import threading
import logging
import funcs
import requests
import typing as tp
from flask import Flask, request, Response
from flask_restful import Api, Resource
from Worker import Worker

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    filename="spoke-daemon.log",
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
        event_dict = request.get_data()
        logging.debug(f"Received event dict:\n{event_dict}")

        # identify, from which device the input is coming from
        known_hid_devices: tp.Dict[str, str] = config["known_hid_devices"]
        sender = ""  # name of the sender device

        for device in zip(known_hid_devices):
            if device[1] == event_dict["name"]:
                sender = device[0]
                break

        if not sender:
            logging.error("Sender of the event dict is not mentioned in the config. Can't handle the request.")
            return

        # handle the event in accord with it's source
        if sender == "rfid_reader":
            # if worker is logged in - log him out
            global worker, display
            if worker.is_authorized:
                worker.log_out()
                display.state = 0
                return

            # todo
            # make a call to authorize the worker otherwise
            pass

        # todo
        elif sender == "barcode_reader":
            pass


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
