import atexit
import json
import logging
import typing as tp

import requests
from flask import Flask, Response, request
from flask_restful import Api, Resource

from exceptions import BackendUnreachableError
from feecc_spoke import Views
from feecc_spoke.Display import Display
from feecc_spoke.Employee import Employee
from feecc_spoke.Spoke import Spoke

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s (%(asctime)s) [%(module)s:%(funcName)s]: %(message)s",
)

spoke: Spoke = Spoke()  # initialize Spoke object
worker: Employee = Employee()  # create Employee object
display: Display = Display(worker, spoke)  # instantiate Display
app = Flask(__name__)  # create a Flask app
api = Api(app)  # create a Flask API


@atexit.register  # define the behaviour when the script execution is completed
def end_session() -> None:
    """clear the display, release SPI and join the thread before exiting"""
    display.end_session()


def send_request_to_backend(url: str, payload: tp.Dict[str, tp.Any]) -> tp.Dict[str, tp.Any]:
    """try sending request, display error message on failure"""
    try:
        response = requests.post(url=url, json=payload)
        response_data = response.json()
        return dict(response_data)

    except Exception as E:
        logging.error(f"Backend unreachable: {E}")

        previous_view: tp.Optional[tp.Type[Views.View]] = display.current_view
        display.render_view(Views.BackendUnreachableAlert)

        if previous_view is not None:
            display.render_view(previous_view)

        raise BackendUnreachableError


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
            logging.info("Ignoring barcode event: worker not authorized.")
            display.render_view(Views.AuthorizeFirstAlert)
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

                try:
                    response_data = send_request_to_backend(url, payload)
                    display.render_view(Views.LoginScreen)
                except BackendUnreachableError:
                    return

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
                display.render_view(Views.UnitNotFoundAlert)
                display.render_view(Views.AwaitInputScreen)

        except Exception as E:
            logging.error(f"Request to the hub failed:\n{E}")

    @staticmethod
    def _handle_rfid_event(event_dict: tp.Dict[str, tp.Any]) -> None:
        # if worker is logged in - log him out
        if worker.is_authorized:
            spoke.end_recording()

            payload = {"workbench_no": spoke.number}
            url = f"{spoke.hub_url}/api/employee/log-out"

            try:
                send_request_to_backend(url, payload)
                worker.log_out()
                display.render_view(Views.SuccessfulLogOutAlert)
                display.render_view(Views.LoginScreen)
            except BackendUnreachableError:
                pass

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

                try:
                    response_data = send_request_to_backend(url, payload)
                except BackendUnreachableError:
                    return

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
            display.render_view(Views.SuccessfulAuthorizationAlert)
            display.render_view(Views.AwaitInputScreen)
        else:
            display.render_view(Views.FailedAuthorizationAlert)
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
    app.run(host=spoke.config["api"]["server_ip"], port=spoke.config["api"]["server_port"])
    display.render_view(Views.LoginScreen)
