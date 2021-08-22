import atexit
import typing as tp

from flask import Flask, request
from flask_restful import Api, Resource
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from feecc_spoke import Alerts, Views
from feecc_spoke.Display import Display
from feecc_spoke.Employee import Employee
from feecc_spoke.Exceptions import BackendUnreachableError
from feecc_spoke.Spoke import Spoke
from feecc_spoke.State import AuthorizedIdling, AwaitLogin, ProductionStageOngoing
from feecc_spoke.Types import AddInfo, RequestPayload

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

    def post(self) -> None:
        """Parse the event dict JSON"""
        event_dict: RequestPayload = request.get_json()  # type: ignore
        logger.debug(f"Received event dict:\n{event_dict}")
        # handle the event in accord with it's source
        sender = Spoke().identify_sender(event_dict["name"])
        if sender == "rfid_reader":
            self._handle_rfid_event(event_dict)
        elif sender == "barcode_reader":
            self._handle_barcode_event(event_dict["string"])
        else:
            logger.error("Sender of the event dict is not mentioned in the config. Can't handle the request.")

    @staticmethod
    def _handle_rfid_event(event_dict: RequestPayload) -> None:
        """RFID event handling"""
        # resolve sync conflicts
        try:
            workbench_status: RequestPayload = Spoke().workbench_status
            if not Employee().is_authorized == workbench_status["employee_logged_in"]:
                sync_login_status()
        except BackendUnreachableError as E:
            logger.error(f"Failed to handle RFID event: {E}, event: {event_dict}")
            pass

        if Spoke().state_class in [AuthorizedIdling, ProductionStageOngoing]:
            # if worker is logged in - log him out
            Spoke().state.end_shift(event_dict["string"])
        elif Spoke().state_class is AwaitLogin:
            # make a call to authorize the worker otherwise
            rfid_card_id: str = str(event_dict["string"])
            Spoke().state.start_shift(rfid_card_id)

    @staticmethod
    def _handle_barcode_event(barcode_string: str, additional_info: tp.Optional[AddInfo] = None) -> None:
        """Barcode event handling"""
        logger.debug(f"Handling barcode event. EAN: {barcode_string}, additional_info: {additional_info or 'is empty'}")

        if Spoke().state_class is AuthorizedIdling:
            logger.info(f"Starting an operation for unit with int. id {barcode_string}")
            Spoke().state.start_operation(barcode_string, additional_info)
        elif Spoke().state_class is ProductionStageOngoing:
            logger.info(f"Ending an operation for unit with int. id {barcode_string}")
            Spoke().state.end_operation(barcode_string, additional_info)
        else:
            logger.error(
                f"Nothing to do for unit with int. id {barcode_string}. Ignoring event since no one is authorized."
            )


api.add_resource(HidEventHandler, "/api/hid_event")


def sync_login_status(no_feedback: bool = False) -> None:
    """resolve conflicts in login status between backend and local data"""
    try:
        # get data from the backend
        workbench_status: RequestPayload = Spoke().workbench_status
        is_logged_in: bool = bool(workbench_status["employee_logged_in"])

        # identify conflicts and treat accordingly
        if is_logged_in == Employee().is_authorized:
            logger.debug("local and global login statuses match. no discrepancy found.")
        elif is_logged_in and not Employee().is_authorized:
            logger.info("Employee is logged in on the backend. Logging in locally.")
            employee_data: tp.Dict[str, str] = workbench_status["employee"]
            Employee().log_in(employee_data["position"], employee_data["name"], "")
        elif not is_logged_in and Employee().is_authorized:
            logger.info("Employee is logged out on the backend. Logging out locally.")
            Employee().log_out()
    except BackendUnreachableError:
        pass
    except Exception as E:
        logger.error(f"Login sync failed: {E}")

    # display feedback accordingly
    if no_feedback:
        pass
    elif Employee().is_authorized:
        Display().render_view(Alerts.SuccessfulAuthorizationAlert)
        Display().render_view(Alerts.ScanBarcodeAlert)
    else:
        Display().render_view(Views.LoginScreen)


# daemon initialization
if __name__ == "__main__":
    Display()  # instantiate Display
    logger.info("Syncing login status")
    sync_login_status()
    logger.info("Starting server")
    server_ip: str = Spoke().config["api"]["server_ip"]
    server_port: int = int(Spoke().config["api"]["server_port"])
    app.run(host=server_ip, port=server_port)
