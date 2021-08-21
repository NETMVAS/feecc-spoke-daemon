import atexit
import json
import typing as tp

import requests
from flask import Flask, Response, request
from flask_restful import Api, Resource
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from exceptions import BackendUnreachableError
from feecc_spoke import Alerts, ViewBase, Views
from feecc_spoke.Display import Display
from feecc_spoke.Employee import Employee
from feecc_spoke.Spoke import Spoke
from Types import AddInfo, RequestPayload

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

# REST API endpoints
app = Flask(__name__)  # create a Flask app
api = Api(app)  # create a Flask API


@atexit.register
def end_session() -> None:
    """
    log out the worker, clear the display, release SPI and join the thread before exiting
    """
    logger.info("SIGTERM handling started")
    if Employee().is_authorized:
        logger.info("Employee logged in. Logging out before exiting.")
        HidEventHandler().log_out(Employee().rfid_card_id)
    Display().end_session()
    logger.info("SIGTERM handling finished")


def send_request_to_backend(url: str, payload: RequestPayload) -> RequestPayload:
    """try sending request, display error message on failure"""
    try:
        response = requests.post(url=url, json=payload, timeout=1)
        response_data = response.json()
        return dict(response_data)

    except Exception as E:
        logger.error(f"Backend unreachable: {E}")

        previous_view: tp.Optional[tp.Type[ViewBase.View]] = (
            Display().current_view.__class__ if Display().current_view is not None else None  # type: ignore
        )
        Display().render_view(Alerts.BackendUnreachableAlert)

        if previous_view is not None:
            Display().render_view(previous_view)

        raise BackendUnreachableError


class HidEventHandler(Resource):
    """handles RFID and barcode scanner events"""

    def post(self) -> None:
        # parse the event dict JSON
        event_dict: RequestPayload = request.get_json()  # type: ignore
        logger.debug(f"Received event dict:\n{event_dict}")

        # handle the event in accord with it's source
        sender = Spoke().identify_sender(event_dict["name"])

        if sender == "rfid_reader":
            self._handle_rfid_event(event_dict)
        elif sender == "barcode_reader":
            self._handle_barcode_event(event_dict)
        else:
            logger.error(
                "Sender of the event dict is not mentioned in the config. Can't handle the request."
            )

    def _handle_rfid_event(self, event_dict: RequestPayload) -> None:
        # resolve sync conflicts
        try:
            workbench_status: RequestPayload = Spoke().workbench_status
            if not Employee().is_authorized == workbench_status["employee_logged_in"]:
                sync_login_status()
        except BackendUnreachableError:
            pass

        # if worker is logged in - log him out
        if Employee().is_authorized:
            self.log_out(event_dict["string"])
            return

        # perform development log in if set in config
        if Spoke().disable_id_validation:
            logger.info("Employee authorized regardless of the ID card: development auth is on.")
            Employee().log_in("Младший инженер", "Иванов Иван Иванович", "000000000000000000")
        else:
            # make a call to authorize the worker otherwise
            self.log_in(event_dict)

        # display corresponding messages
        if Employee().is_authorized:
            Display().render_view(Alerts.SuccessfulAuthorizationAlert)
            Display().render_view(Alerts.ScanBarcodeAlert)
        else:
            Display().render_view(Alerts.FailedAuthorizationAlert)
            Display().render_view(Views.LoginScreen)

    def _handle_barcode_event(self, event_dict: RequestPayload) -> None:
        # ignore the event if unauthorized
        if not Employee().is_authorized:
            logger.info("Ignoring barcode event: Employee() not authorized.")
            Display().render_view(Alerts.AuthorizeFirstAlert)
            Display().render_view(Views.LoginScreen)
            return

        # make a request to the hub regarding the barcode
        barcode_string = event_dict["string"]
        logger.info(f"Making a request to hub regarding the barcode {barcode_string}")
        response_data: RequestPayload = self._barcode_handling(barcode_string)
        self._post_barcode_handling(response_data)

    def _barcode_handling(self, barcode_string: str) -> RequestPayload:
        if Spoke().operation_ongoing:
            response_data: RequestPayload = self.end_operation(barcode_string)
            if Spoke().config["general"]["send_upload_request"]:
                self._send_upload_request(barcode_string)
            return response_data
        else:
            return self.start_operation(barcode_string)

    @staticmethod
    def start_operation(barcode_string: str, additional_info: AddInfo = None) -> RequestPayload:
        """send a request to start operation on the provided unit"""
        Spoke().associated_unit_internal_id = barcode_string
        if Spoke().disable_barcode_validation:
            return {"status": True}
        url = f"{Spoke().hub_url}/api/unit/{barcode_string}/start"
        payload = {
            "workbench_no": Spoke().number,
            "production_stage_name": Spoke().config["general"]["production_stage_name"],
            "additional_info": additional_info if additional_info else {},
        }
        try:
            return send_request_to_backend(url, payload)
        except BackendUnreachableError:
            return {"status": False}

    @staticmethod
    def end_operation(barcode_string: str, additional_info: AddInfo = None) -> RequestPayload:
        """send a request to end operation on the provided unit"""
        Spoke().associated_unit_internal_id = None
        if Spoke().disable_barcode_validation:
            return {"status": True}
        url = f"{Spoke().hub_url}/api/unit/{barcode_string}/end"
        payload = {
            "workbench_no": Spoke().number,
            "additional_info": additional_info if additional_info else {},
        }
        try:
            return send_request_to_backend(url, payload)
        except BackendUnreachableError:
            return {"status": False}

    @staticmethod
    def _post_barcode_handling(response_data: RequestPayload) -> None:
        """display feedback on the performed requests"""
        if not response_data["status"]:
            logger.error(f"Barcode validation failed: hub returned '{response_data['comment']}'")
            Display().render_view(Alerts.UnitNotFoundAlert)
            Display().render_view(Alerts.ScanBarcodeAlert)
        else:
            # end ongoing operation if there is one
            if Spoke().operation_ongoing:
                # switch to ongoing operation screen since validation succeeded
                logger.info("Starting operation.")
                Display().render_view(Alerts.OperationStartedAlert)
                Display().render_view(Views.OngoingOperationScreen)
            else:
                # switch back to await screen
                logger.info("Operation in progress. Stopping.")
                Display().render_view(Alerts.OperationEndedAlert)
                Display().render_view(Alerts.ScanBarcodeAlert)

    @staticmethod
    def send_log_out_request() -> None:
        payload = {"workbench_no": Spoke().number}
        url = f"{Spoke().hub_url}/api/employee/log-out"
        send_request_to_backend(url, payload)

    @staticmethod
    def _send_upload_request(unit_internal_id: str) -> RequestPayload:
        """send a request to upload the unit data"""
        payload = {"workbench_no": Spoke().number}
        url = f"{Spoke().hub_url}/api/unit/{unit_internal_id}/upload"
        return send_request_to_backend(url, payload)

    def log_out(self, rfid_card_id: str) -> None:
        """log employee out"""
        try:
            if Spoke().operation_ongoing:
                HidEventHandler.end_operation(str(Spoke().associated_unit_internal_id))
                Spoke().associated_unit_internal_id = None
            if not Spoke().disable_id_validation:
                self.send_log_out_request()

            if any(
                (
                    Employee().rfid_card_id == rfid_card_id,
                    not Employee().rfid_card_id,
                    Spoke().disable_id_validation,
                )
            ):
                Employee().log_out()
                Display().render_view(Alerts.SuccessfulLogOutAlert)
                Display().render_view(Views.LoginScreen)
            else:
                Display().render_view(Alerts.IdMismatchAlert)
                Display().render_view(Alerts.ScanBarcodeAlert)

        except BackendUnreachableError:
            pass

    @staticmethod
    def send_log_in_request(rfid_card_no: str) -> RequestPayload:
        payload = {
            "workbench_no": Spoke().number,
            "employee_rfid_card_no": rfid_card_no,
        }
        url = f"{Spoke().hub_url}/api/employee/log-in"
        try:
            return send_request_to_backend(url, payload)
        except BackendUnreachableError:
            return {"status": False}

    def log_in(self, event_dict: RequestPayload) -> None:
        """log employee in"""
        rfid_card_id: str = str(event_dict["string"])
        response_data: RequestPayload = self.send_log_in_request(rfid_card_id)

        # check if worker authorized and log him in
        if response_data["status"]:
            name = response_data["employee_data"]["name"]
            position = response_data["employee_data"]["position"]
            Employee().log_in(position, name, rfid_card_id)
        else:
            logger.error("Employee could not be authorized: hub rejected ID card")


class ResetState(Resource):
    """resets Spoke state back to 0 in case of a corresponding POST request"""

    @staticmethod
    def post() -> Response:
        Display().render_view(Views.LoginScreen)
        message = {"message": "Successful state reset"}
        payload = json.dumps(message)
        return Response(response=payload, status=200)


api.add_resource(HidEventHandler, "/api/hid_event")
api.add_resource(ResetState, "/api/reset_state")


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
    except Exception as e:
        logger.error(f"Login sync failed: {e}")

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
    server_ip: str = Spoke().config["api"]["server_ip"]
    server_port: int = int(Spoke().config["api"]["server_port"])
    logger.info("Syncing login status")
    sync_login_status()
    logger.info("Starting server")
    app.run(host=server_ip, port=server_port)
