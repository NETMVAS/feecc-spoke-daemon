import atexit
import json
import logging
import typing as tp

import requests
from flask import Flask, Response, request
from flask_restful import Api, Resource

from Types import AddInfo, RequestPayload
from exceptions import BackendUnreachableError
from feecc_spoke import Alerts, ViewBase, Views
from feecc_spoke.Display import Display
from feecc_spoke.Employee import Employee
from feecc_spoke.Spoke import Spoke

# set up logging
log_format: str = "%(levelname)s (%(asctime)s) [%(module)s:%(funcName)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=log_format)

# REST API endpoints
app = Flask(__name__)  # create a Flask app
api = Api(app)  # create a Flask API


@atexit.register
def end_session() -> None:
    """
    log out the worker, clear the display, release SPI and join the thread before exiting
    """
    logging.info("SIGTERM handling started")
    if worker.is_authorized:
        logging.info("Employee logged in. Logging out before exiting.")
        HidEventHandler().log_out(worker.rfid_card_id)
    display.end_session()
    logging.info("SIGTERM handling finished")


def send_request_to_backend(url: str, payload: RequestPayload) -> RequestPayload:
    """try sending request, display error message on failure"""
    try:
        response = requests.post(url=url, json=payload, timeout=1)
        response_data = response.json()
        return dict(response_data)

    except Exception as E:
        logging.error(f"Backend unreachable: {E}")

        previous_view: tp.Optional[tp.Type[ViewBase.View]] = (
            display.current_view.__class__ if display.current_view is not None else None
        )
        display.render_view(Alerts.BackendUnreachableAlert)

        if previous_view is not None:
            display.render_view(previous_view)

        raise BackendUnreachableError


class HidEventHandler(Resource):
    """handles RFID and barcode scanner events"""

    def post(self) -> None:
        # parse the event dict JSON
        event_dict: RequestPayload = request.get_json()  # type: ignore
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

    def _handle_rfid_event(self, event_dict: RequestPayload) -> None:
        # resolve sync conflicts
        try:
            workbench_status: RequestPayload = spoke.workbench_status
            if not worker.is_authorized == workbench_status["employee_logged_in"]:
                sync_login_status()
        except BackendUnreachableError:
            pass

        # if worker is logged in - log him out
        if worker.is_authorized:
            self.log_out(event_dict["string"])
            return

        # perform development log in if set in config
        if spoke.config["developer"]["disable_id_validation"]:
            logging.info("Employee authorized regardless of the ID card: development auth is on.")
            worker.log_in("Младший инженер", "Иванов Иван Иванович", "000000000000000000")
        else:
            # make a call to authorize the worker otherwise
            self.log_in(event_dict)

        # display corresponding messages
        if worker.is_authorized:
            display.render_view(Alerts.SuccessfulAuthorizationAlert)
            display.render_view(Views.AwaitInputScreen)
        else:
            display.render_view(Alerts.FailedAuthorizationAlert)
            display.render_view(Views.LoginScreen)

    def _handle_barcode_event(self, event_dict: RequestPayload) -> None:
        # ignore the event if unauthorized
        if not worker.is_authorized:
            logging.info("Ignoring barcode event: worker not authorized.")
            display.render_view(Alerts.AuthorizeFirstAlert)
            display.render_view(Views.LoginScreen)
            return

        # make a request to the hub regarding the barcode
        barcode_string = event_dict["string"]
        logging.info(f"Making a request to hub regarding the barcode {barcode_string}")
        response_data: RequestPayload = self._barcode_handling(barcode_string)
        self._post_barcode_handling(response_data)

    def _barcode_handling(self, barcode_string: str) -> RequestPayload:
        if spoke.operation_ongoing:
            return self.end_operation(barcode_string)
        else:
            return self.start_operation(barcode_string)

    @staticmethod
    def start_operation(barcode_string: str, additional_info: AddInfo = None) -> RequestPayload:
        """send a request to start operation on the provided unit"""
        spoke.associated_unit_internal_id = barcode_string
        if spoke.config["developer"]["disable_barcode_validation"]:
            return {"status": True}
        url = f"{spoke.hub_url}/api/unit/{barcode_string}/start"
        payload = {
            "workbench_no": spoke.number,
            "production_stage_name": spoke.config["general"]["production_stage_name"],
            "additional_info": additional_info if additional_info else {},
        }
        try:
            return send_request_to_backend(url, payload)
        except BackendUnreachableError:
            return {"status": False}

    @staticmethod
    def end_operation(barcode_string: str, additional_info: AddInfo = None) -> RequestPayload:
        """send a request to end operation on the provided unit"""
        spoke.associated_unit_internal_id = None
        if spoke.config["developer"]["disable_barcode_validation"]:
            return {"status": True}
        url = f"{spoke.hub_url}/api/unit/{barcode_string}/end"
        payload = {
            "workbench_no": spoke.number,
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
            logging.error(f"Barcode validation failed: hub returned '{response_data['comment']}'")
            display.render_view(Alerts.UnitNotFoundAlert)
            display.render_view(Views.AwaitInputScreen)
        else:
            # end ongoing operation if there is one
            if spoke.operation_ongoing:
                # switch to ongoing operation screen since validation succeeded
                logging.info("Starting operation.")
                display.render_view(Alerts.OperationStartedAlert)
                display.render_view(Views.OngoingOperationScreen)
            else:
                # switch back to await screen
                logging.info("Operation in progress. Stopping.")
                display.render_view(Alerts.OperationEndedAlert)
                display.render_view(Views.AwaitInputScreen)

    @staticmethod
    def send_log_out_request() -> None:
        payload = {"workbench_no": spoke.number}
        url = f"{spoke.hub_url}/api/employee/log-out"
        send_request_to_backend(url, payload)

    def log_out(self, rfid_card_id: str) -> None:
        """log employee out"""
        try:
            if spoke.operation_ongoing:
                HidEventHandler.end_operation(str(spoke.associated_unit_internal_id))
                spoke.associated_unit_internal_id = None
            if not spoke.config["developer"]["disable_id_validation"]:
                self.send_log_out_request()

            if worker.rfid_card_id == rfid_card_id or not worker.rfid_card_id:
                worker.log_out()
                display.render_view(Alerts.SuccessfulLogOutAlert)
                display.render_view(Views.LoginScreen)
            else:
                display.render_view(Alerts.IdMismatchAlert)
                display.render_view(Views.AwaitInputScreen)

        except BackendUnreachableError:
            pass

    @staticmethod
    def send_log_in_request(rfid_card_no: str) -> RequestPayload:
        payload = {
            "workbench_no": spoke.number,
            "employee_rfid_card_no": rfid_card_no,
        }
        url = f"{spoke.hub_url}/api/employee/log-in"
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
            worker.log_in(position, name, rfid_card_id)
        else:
            logging.error("Employee could not be authorized: hub rejected ID card")


class ResetState(Resource):
    """resets Spoke state back to 0 in case of a corresponding POST request"""

    @staticmethod
    def post() -> Response:
        display.render_view(Views.LoginScreen)
        message = {"message": "Successful state reset"}
        payload = json.dumps(message)
        return Response(response=payload, status=200)


api.add_resource(HidEventHandler, "/api/hid_event")
api.add_resource(ResetState, "/api/reset_state")


def sync_login_status(no_feedback: bool = False) -> None:
    """resolve conflicts in login status between backend and local data"""
    try:
        # get data from the backend
        workbench_status: RequestPayload = spoke.workbench_status
        is_logged_in: bool = bool(workbench_status["employee_logged_in"])

        # identify conflicts and treat accordingly
        if is_logged_in == worker.is_authorized:
            logging.debug("local and global login statuses match. no discrepancy found.")
        elif is_logged_in and not worker.is_authorized:
            logging.info("Employee is logged in on the backend. Logging in locally.")
            employee_data: tp.Dict[str, str] = workbench_status["employee"]
            worker.log_in(employee_data["position"], employee_data["name"], "")
        elif not is_logged_in and worker.is_authorized:
            logging.info("Employee is logged out on the backend. Logging out locally.")
            worker.log_out()
    except BackendUnreachableError:
        pass
    except Exception as e:
        logging.error(f"Login sync failed: {e}")

    # display feedback accordingly
    if no_feedback:
        pass
    elif worker.is_authorized:
        display.render_view(Alerts.SuccessfulAuthorizationAlert)
        display.render_view(Views.AwaitInputScreen)
    else:
        display.render_view(Views.LoginScreen)


# daemon initialization
if __name__ == "__main__":
    spoke: Spoke = Spoke()  # initialize Spoke object
    worker: Employee = Employee()  # create Employee object
    display: Display = Display(worker, spoke)  # instantiate Display
    server_ip: str = spoke.config["api"]["server_ip"]
    server_port: int = int(spoke.config["api"]["server_port"])
    logging.info("Syncing login status")
    sync_login_status()
    logging.info("Starting server")
    app.run(host=server_ip, port=server_port)
