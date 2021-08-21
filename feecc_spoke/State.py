from __future__ import annotations

import typing as tp
from abc import ABC, abstractmethod

import requests
from loguru import logger

from . import Alerts, ViewBase, Views
from .Display import Display
from .Employee import Employee
from .Exceptions import BackendUnreachableError, StateForbiddenError
from .Spoke import Spoke
from .Types import AddInfo, RequestPayload


class State(ABC):
    """abstract State class for states to inherit from"""

    @property
    def context(self) -> Spoke:
        return Spoke()

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def description(self) -> str:
        """returns own docstring which describes the state"""
        return self.__doc__ or ""

    @abstractmethod
    @tp.no_type_check
    def perform_on_apply(self, *args, **kwargs) -> None:
        """state action executor (to be overridden)"""
        raise NotImplementedError

    @tp.no_type_check
    def start_shift(self, rfid_card_id: str) -> None:
        """log employee in"""
        response_data: RequestPayload

        logger.info(f"Got login request. RFID Card ID: {rfid_card_id}")

        if Spoke().disable_id_validation:
            # perform development log in if set in config
            logger.info("Employee authorized regardless of the ID card: development auth is on.")
            response_data = {
                "status": True,
                "employee_data": {
                    "name": "Иванов Иван Иванович",
                    "position": "Младший инженер",
                },
            }
        else:
            response_data = self._send_log_in_request(rfid_card_id)

        # check if worker authorized and log him in
        if response_data["status"]:
            name: str = str(response_data["employee_data"]["name"])
            position: str = str(response_data["employee_data"]["position"])
            Employee().log_in(position, name, rfid_card_id)
            Display().render_view(Alerts.SuccessfulAuthorizationAlert)
            self.context.apply_state(AuthorizedIdling)
        else:
            logger.error(f"Employee could not be authorized: {response_data['comment']}")
            Display().render_view(Alerts.FailedAuthorizationAlert)
            Display().render_view(Views.LoginScreen)

    @tp.no_type_check
    def end_shift(self, rfid_card_id: str) -> None:
        """log employee out"""

        logger.info(f"Trying to logout employee with RFID card ID: {rfid_card_id}")

        try:
            if not Spoke().disable_id_validation:
                self._send_log_out_request()

            if any(
                (
                    Employee().rfid_card_id == rfid_card_id,
                    not Employee().rfid_card_id,
                    Spoke().disable_id_validation,
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
    def start_operation(self, barcode_string: str, additional_info: AddInfo = None) -> None:
        """send a request to start operation on the provided unit"""
        Spoke().associated_unit_internal_id = barcode_string
        if Spoke().disable_barcode_validation:
            return

        url = f"{Spoke().hub_url}/api/unit/{barcode_string}/start"
        payload = {
            "workbench_no": Spoke().number,
            "production_stage_name": Spoke().config["general"]["production_stage_name"],
            "additional_info": additional_info if additional_info else {},
        }

        try:
            self._send_request_to_backend(url, payload)
        except BackendUnreachableError as E:
            logger.error(f"Backend unreachable: {E}")
            return

        self.context.apply_state(ProductionStageOngoing)

    @tp.no_type_check
    def end_operation(self, barcode_string: str, additional_info: AddInfo = None):
        """send a request to end operation on the provided unit"""
        Spoke().associated_unit_internal_id = None
        if Spoke().disable_barcode_validation:
            self.context.apply_state(AuthorizedIdling)
            return
        url = f"{Spoke().hub_url}/api/unit/{barcode_string}/end"
        payload = {
            "workbench_no": Spoke().number,
            "additional_info": additional_info if additional_info else {},
        }
        try:
            self._send_request_to_backend(url, payload)
            if Spoke().config["general"]["send_upload_request"]:
                self._send_upload_request(barcode_string)
            Display().render_view(Alerts.OperationEndedAlert)
            self.context.apply_state(AuthorizedIdling)
        except BackendUnreachableError as E:
            logger.error(f"Backend unreachable: {E}")

    @staticmethod
    def _state_forbidden(message: tp.Optional[str] = None) -> None:
        """Display a message about an operation forbidden by the state"""
        msg: str = f"Operation forbidden by the state. Details: {message}"
        logger.error(msg)
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
            previous_view: tp.Optional[tp.Type[ViewBase.View]] = (
                None if not Display().current_view else Display().current_view.__class__  # type: ignore
            )
            Display().render_view(Alerts.BackendUnreachableAlert)

            if previous_view is not None:
                Display().render_view(previous_view)

            raise BackendUnreachableError

    def _send_log_out_request(self) -> None:
        payload = {"workbench_no": Spoke().number}
        url = f"{Spoke().hub_url}/api/employee/log-out"
        self._send_request_to_backend(url, payload)

    def _send_upload_request(self, unit_internal_id: str) -> RequestPayload:
        """send a request to upload the unit data"""
        payload = {"workbench_no": Spoke().number}
        url = f"{Spoke().hub_url}/api/unit/{unit_internal_id}/upload"
        return self._send_request_to_backend(url, payload)

    def _send_log_in_request(self, rfid_card_no: str) -> RequestPayload:
        payload = {
            "workbench_no": Spoke().number,
            "employee_rfid_card_no": rfid_card_no,
        }
        url = f"{Spoke().hub_url}/api/employee/log-in"
        try:
            return self._send_request_to_backend(url, payload)
        except BackendUnreachableError as E:
            logger.error(f"Backend unreachable: {E}")
            return {"status": False}


class AwaitLogin(State, ABC):
    """State when the workbench is empty and waiting for an employee authorization"""

    def perform_on_apply(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        Display().render_view(Views.LoginScreen)

    def end_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot log out: no one is logged in at the workbench."
        self._state_forbidden(msg)

    def start_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
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
        self._state_forbidden(msg)

    def end_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot log out: there is an ongoing operation at the workbench."
        self._state_forbidden(msg)

    def start_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg: str = "Cannot start an operation: there is already an ongoing operation at the workbench."
        self._state_forbidden(msg)
