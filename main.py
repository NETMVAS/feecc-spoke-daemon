import atexit

from flask import Flask, request
from flask_restful import Api, Resource
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from feecc_spoke.Display import Display
from feecc_spoke.Employee import Employee
from feecc_spoke.Exceptions import StateForbiddenError
from feecc_spoke.Spoke import Spoke
from feecc_spoke.Types import RequestPayload

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

# REST API endpoints
app = Flask(__name__)  # create a Flask app
api = Api(app)  # create a Flask API


@atexit.register
def end_session() -> None:
    """log out the worker, clear the display, release SPI and join the thread before exiting"""
    logger.info("SIGTERM handling started")
    if Employee().is_authorized:
        logger.info("Employee logged in. Logging out before exiting.")
        Spoke().state.end_shift(Employee().rfid_card_id)
    Display().end_session()
    logger.info("SIGTERM handling finished")


class HidEventHandler(Resource):
    """Handles RFID and barcode scanner events"""

    @staticmethod
    def post() -> None:
        """Parse the event dict JSON"""
        event_dict: RequestPayload = request.get_json()  # type: ignore
        logger.debug(f"Received event dict:\n{event_dict}")
        # handle the event in accord with it's source
        sender = Spoke().identify_sender(event_dict["name"])

        try:
            if sender == "rfid_reader":
                Spoke().handle_rfid_event(event_dict)
            elif sender == "barcode_reader":
                Spoke().handle_barcode_event(event_dict["string"])
            else:
                logger.error("Sender of the event dict is not mentioned in the config. Can't handle the request.")
        except StateForbiddenError:
            pass


api.add_resource(HidEventHandler, "/api/hid_event")

# daemon initialization
if __name__ == "__main__":
    Display()  # instantiate Display
    logger.info("Syncing login status")
    Spoke().sync_login_status()
    logger.info("Starting server")
    server_ip: str = Spoke().config["api"]["server_ip"]
    server_port: int = int(Spoke().config["api"]["server_port"])
    app.run(host=server_ip, port=server_port)
