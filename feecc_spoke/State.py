from __future__ import annotations

from copy import copy
import typing as tp
from abc import ABC, abstractmethod

import requests
from loguru import logger

from . import Alerts, ViewBase, Views
from .Display import Display
from .Employee import Employee
from .Exceptions import BackendUnreachableError, BufferUnfilledError, StateForbiddenError, FailedToCreateUnitError
from .Types import AddInfo, RequestPayload

if tp.TYPE_CHECKING:
    from .Spoke import Spoke


class State(ABC):
    """abstract State class for states to inherit from"""

    def __init__(self, spoke: Spoke) -> None:
        self._spoke: Spoke = spoke
        self._qr_buffer: tp.List[str] = []

    @property
    def buffer_ready(self) -> bool:
        return len(self._spoke.config["new_unit_creation_settings"]["modules"]) == len(self.qr_buffer)

    @property
    def qr_buffer(self) -> tp.List[str]:
        if self.buffer_ready:
            buffer = copy(self._qr_buffer)
            self._qr_buffer = []
            return buffer

        raise BufferUnfilledError(
            f"Buffer is not fully filled. Progress: "
            f"{len(self._qr_buffer)}/{len(self._spoke.config['new_unit_creation_settings']['modules'])}"
        )

    @qr_buffer.setter
    def qr_buffer(self, link: str) -> None:
        self._qr_buffer.append(link)

    @property
    def context(self) -> Spoke:
        return self._spoke

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    @tp.no_type_check
    def perform_on_apply(self, *args, **kwargs) -> None:
        """state action executor (to be overridden)"""
        raise NotImplementedError

    @tp.no_type_check
    def start_shift(
        self,
        rfid_card_id: str,
        skip_request: bool = False,
        name: tp.Optional[str] = None,
        position: tp.Optional[str] = None,
    ) -> None:
        """log employee in"""
        response_data: RequestPayload
        logger.info(f"Got login request. RFID Card ID: {rfid_card_id}")

        if self._spoke.disable_id_validation:
            # perform development log in if set in config
            logger.info("Employee authorized regardless of the ID card: development auth is on.")
            response_data = {
                "status": True,
                "employee_data": {
                    "name": "Иванов Иван Иванович",
                    "position": "Младший инженер",
                },
            }
        elif skip_request:
            response_data = {
                "status": True,
                "employee_data": {
                    "name": name,
                    "position": position,
                },
            }
        else:
            try:
                response_data = self._send_log_in_request(rfid_card_id)
            except BackendUnreachableError:
                return

        # check if worker authorized and log him in
        if response_data["status"]:
            name_: str = str(response_data["employee_data"]["name"])
            position_: str = str(response_data["employee_data"]["position"])
            Employee().log_in(position_, name_, rfid_card_id)
            Display().render_view(Alerts.SuccessfulAuthorizationAlert)
            self.context.apply_state(AuthorizedIdling)
        else:
            logger.error(f"Employee could not be authorized: {response_data['comment']}")
            Display().render_view(Alerts.FailedAuthorizationAlert)
            Display().render_view(Views.LoginScreen)

    @tp.no_type_check
    def end_shift(self, rfid_card_id: str, skip_card_check: bool = False) -> None:
        """log employee out"""

        logger.info(f"Trying to logout employee with RFID card ID: {rfid_card_id}")

        try:
            if not self._spoke.disable_id_validation and not skip_card_check:
                self._send_log_out_request()

            if any(
                (
                    Employee().rfid_card_id == rfid_card_id,
                    not Employee().rfid_card_id,
                    self._spoke.disable_id_validation,
                    skip_card_check,
                )
            ):
                Employee().log_out()
                Display().render_view(Alerts.SuccessfulLogOutAlert)
                self.context.apply_state(AwaitLogin)
            else:
                Display().render_view(Alerts.IdMismatchAlert)
                Display().render_view(Alerts.ScanBarcodeAlert)

        except BackendUnreachableError as E:
            logger.error(f"Backend unreachable: {E}")
            Display().render_view(Alerts.ScanBarcodeAlert)

    @tp.no_type_check
    def start_operation_on_existing_unit(self, unit_internal_id: str, additional_info: AddInfo = None) -> None:
        """send a request to start operation on the provided unit"""
        self._spoke.associated_unit_internal_id = unit_internal_id

        if not self._spoke.disable_barcode_validation:
            url = f"{self._spoke.hub_url}/api/unit/{unit_internal_id}/start"
            payload = {
                "workbench_no": self._spoke.number,
                "production_stage_name": self._spoke.config["general"]["production_stage_name"],
                "additional_info": additional_info or {},
            }

            try:
                response: RequestPayload = self._send_request_to_backend(url, payload)
                if not response["status"]:
                    logger.error(response)
                    Display().render_view(Alerts.UnitNotFoundAlert)
                    Display().render_view(Alerts.ScanBarcodeAlert)
                    return
            except BackendUnreachableError as E:
                logger.error(f"Backend unreachable: {E}")
                return

        self.context.apply_state(ProductionStageOngoing)

    def create_unit_from_modules(self, module_links: tp.List[str]) -> tp.Tuple[str, tp.Dict[str, str]]:
        """create a new unit featuring scanned module and start an operation on it"""
        config = self._spoke.config["new_unit_creation_settings"]

        # create new unit
        url: str = f"{self._spoke.hub_url}/api/unit/new"
        payload: tp.Dict[str, str] = {"unit_type": config["unit_type"]}
        response: RequestPayload = self._send_request_to_backend(url, payload)
        if not response["status"]:
            message = f"Error creating new unit: {response['comment']}"
            logger.error(message)
            Display().render_view(Alerts.CannotCreateUnitAlert)
            Display().render_view(Alerts.ScanQrCodeAlert)
            raise FailedToCreateUnitError(message)
        unit_internal_id: str = response["unit_internal_id"]

        # gather all modules
        modules: tp.List[str] = self._spoke.config["new_unit_creation_settings"]["modules"]
        module_passports: tp.Dict[str, str] = {}
        for module_name, module_passport_url in zip(modules, module_links):
            module_passports[module_name] = module_passport_url

        return unit_internal_id, module_passports

    @tp.no_type_check
    def end_operation(self, barcode_string: str, additional_info: AddInfo = None):
        """send a request to end operation on the provided unit"""
        self._spoke.associated_unit_internal_id = None
        if self._spoke.disable_barcode_validation:
            self.context.apply_state(AuthorizedIdling)
            return
        url = f"{self._spoke.hub_url}/api/unit/{barcode_string}/end"
        payload = {
            "workbench_no": self._spoke.number,
            "additional_info": additional_info or {},
        }
        try:
            self._send_request_to_backend(url, payload)
            if self._spoke.config["general"]["send_upload_request"]:
                self._send_upload_request(barcode_string)
            Display().render_view(Alerts.OperationEndedAlert)
            self.context.apply_state(AuthorizedIdling)
        except BackendUnreachableError as E:
            logger.error(f"Backend unreachable: {E}")

    @staticmethod
    def _state_forbidden(message: tp.Optional[str] = None, display_alert: bool = True) -> None:
        """Display a message about an operation forbidden by the state"""
        msg: str = f"Operation forbidden by the state. Details: {message}"
        logger.error(msg)

        if display_alert:
            Display().render_view(Alerts.OperationForbiddenAlert)

        raise StateForbiddenError(msg)

    @staticmethod
    def _send_request_to_backend(url: str, payload: RequestPayload) -> RequestPayload:
        """try sending request, display error message on failure"""
        try:
            response = requests.post(url=url, json=payload, timeout=1)
            response_data = response.json()
            return dict(response_data)

        except Exception as E:
            logger.error(f"Backend unreachable: {E}")
            previous_view: tp.Optional[tp.Type[ViewBase.View]] = Display().current_view_class
            Display().render_view(Alerts.BackendUnreachableAlert)

            if previous_view is not None:
                Display().render_view(previous_view)

            raise BackendUnreachableError

    def _send_log_out_request(self) -> None:
        payload = {"workbench_no": self._spoke.number}
        url = f"{self._spoke.hub_url}/api/employee/log-out"
        self._send_request_to_backend(url, payload)

    def _send_upload_request(self, unit_internal_id: str) -> RequestPayload:
        """send a request to upload the unit data"""
        payload = {"workbench_no": self._spoke.number}
        url = f"{self._spoke.hub_url}/api/unit/{unit_internal_id}/upload"
        return self._send_request_to_backend(url, payload)

    def _send_log_in_request(self, rfid_card_no: str) -> RequestPayload:
        payload = {
            "workbench_no": self._spoke.number,
            "employee_rfid_card_no": rfid_card_no,
        }
        url = f"{self._spoke.hub_url}/api/employee/log-in"
        try:
            return self._send_request_to_backend(url, payload)
        except BackendUnreachableError:
            return {"status": False, "comment": "Backend is unreachable"}


class AwaitLogin(State, ABC):
    """State when the workbench is empty and waiting for an employee authorization"""

    def perform_on_apply(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        Display().render_view(Views.LoginScreen)

    def end_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot log out: no one is logged in at the workbench."
        self._state_forbidden(msg)

    def start_operation_on_existing_unit(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot start operation: no one is logged in at the workbench"
        self._state_forbidden(msg)

    def end_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot end operation: no one is logged in at the workbench"
        self._state_forbidden(msg)


class AuthorizedIdling(State):
    """State when an employee was authorized at the workbench but doing nothing"""

    def perform_on_apply(self) -> None:
        Display().render_view(Alerts.ScanBarcodeAlert)

    def start_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot log in: a worker is already logged in at the workbench."
        self._state_forbidden(msg)

    def end_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot end operation: there is no ongoing operation at the workbench."
        self._state_forbidden(msg)


class ProductionStageOngoing(State):
    """State when job is ongoing"""

    def perform_on_apply(self) -> None:
        Display().render_view(Alerts.OperationStartedAlert)
        Display().render_view(Views.OngoingOperationScreen)

    def start_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot log in: a worker is already logged in at the workbench."
        self._state_forbidden(msg, False)

    def end_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot log out: there is an ongoing operation at the workbench."
        self._state_forbidden(msg, False)

    def start_operation_on_existing_unit(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot start an operation: there is already an ongoing operation at the workbench."
        self._state_forbidden(msg, False)
