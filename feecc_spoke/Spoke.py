from __future__ import annotations

import threading
import typing as tp
from random import randint

import requests
from loguru import logger

from . import Alerts, Views, utils
from .Display import Display
from .Employee import Employee
from .Exceptions import BackendUnreachableError
from .State import AuthorizedIdling, AwaitLogin, ProductionStageOngoing, State
from .Types import AddInfo, Config, RequestPayload
from ._Singleton import SingletonMeta


class Spoke(metaclass=SingletonMeta):
    """stores device's status and operational data"""

    def __init__(self) -> None:
        # core attributes
        self.config: Config = utils.get_config()
        self.associated_unit_internal_id: tp.Optional[str] = None
        self.state: State = AwaitLogin(self)
        self._state_thread_list: tp.List[threading.Thread] = []
        self.hid_buffer: str = ""

        # shortcuts to various config parameters
        self.create_new_unit: bool = bool(self.config["general"]["create_new_unit"])
        self.workbench_number: int = int(self.config["general"]["workbench_no"])
        self.hub_url: str = str(self.config["endpoints"]["hub_socket"])
        self.disable_barcode_validation: bool = bool(self.config["developer"]["disable_barcode_validation"])
        self.disable_id_validation: bool = bool(self.config["developer"]["disable_id_validation"])

    @property
    def operation_ongoing(self) -> bool:
        return self.associated_unit_internal_id is not None

    @property
    def workbench_status(self) -> RequestPayload:
        url: str = f"{self.hub_url}/api/workbench/{self.workbench_number}/status"
        try:
            workbench_status: RequestPayload = requests.get(url, timeout=1).json()
            return workbench_status
        except Exception as E:
            message = f"Backend unreachable: {E}"
            logger.error(message)
            raise BackendUnreachableError(message)

    @property
    def _state_thread(self) -> tp.Optional[threading.Thread]:
        return self._state_thread_list[-1] if self._state_thread_list else None

    @_state_thread.setter
    def _state_thread(self, state_thread: threading.Thread) -> None:
        self._state_thread_list.append(state_thread)
        thread_list = self._state_thread_list
        logger.debug(
            f"Attribute _state_thread_list of WorkBench is now of len {len(thread_list)}:\n"
            f"{[repr(t) for t in thread_list]}\n"
            f"Threads alive: {list(filter(lambda t: t.is_alive(), thread_list))}"
        )

    @property
    def state_class(self) -> tp.Type[State]:
        return self.state.__class__

    def sync_login_status(self, no_feedback: bool = False) -> None:
        """resolve conflicts in login status between backend and local data"""
        try:
            # get data from the backend
            workbench_status: RequestPayload = Spoke().workbench_status
            is_logged_in: bool = bool(workbench_status["employee_logged_in"])

            # identify conflicts and treat accordingly
            if is_logged_in and self.state_class is AuthorizedIdling:
                logger.debug("local and global login statuses match. no discrepancy found.")

            elif is_logged_in and self.state_class is AwaitLogin:
                logger.info("Employee is logged in on the backend. Logging in locally.")
                employee_data: tp.Dict[str, str] = workbench_status["employee"]
                self.state.start_shift(
                    "", skip_request=True, position=employee_data["position"], name=employee_data["name"]
                )

            elif not is_logged_in and self.state_class is AuthorizedIdling:
                logger.info("Employee is logged out on the backend. Logging out locally.")
                self.state.end_shift("", skip_card_check=True)

        except BackendUnreachableError:
            pass

        except Exception as E:
            logger.error(f"Login sync failed: {E}")

        # display feedback accordingly
        if no_feedback:
            pass
        elif Employee().is_authorized:
            Display().render_view(Alerts.SuccessfulAuthorizationAlert)
            if self.create_new_unit:
                Display().render_view(Alerts.ScanQrCodeAlert)
            else:
                Display().render_view(Alerts.ScanBarcodeAlert)
        else:
            Display().render_view(Views.LoginScreen)

    def identify_sender(self, sender_device_name: str) -> tp.Optional[str]:
        """identify, which device the input is coming from and if it is known return it's role"""
        known_hid_devices: tp.Dict[str, str] = self.config["known_hid_devices"]

        for sender_name, device_name in known_hid_devices.items():
            if device_name == sender_device_name:
                return sender_name

        return None

    def apply_state(self, state: tp.Type[State], *args: tp.Any, **kwargs: tp.Any) -> None:
        """execute provided state in the background"""
        self.state = state(self)
        logger.info(f"Workbench state is now {self.state.name}")

        # execute state in the background
        thread_name: str = f"{self.state.name}-{randint(1, 999)}"
        logger.debug(f"Trying to execute state: {self.state.name} in thread {thread_name}")
        self._state_thread = threading.Thread(
            target=self.state.perform_on_apply,
            args=args,
            kwargs=kwargs,
            daemon=False,
            name=thread_name,
        )
        self._state_thread.start()

    def handle_rfid_event(self, string: str) -> None:
        """RFID event handling"""
        # resolve sync conflicts
        try:
            workbench_status: RequestPayload = self.workbench_status
            if Employee().is_authorized != workbench_status["employee_logged_in"]:
                self.sync_login_status()
        except BackendUnreachableError as E:
            logger.error(f"Failed to handle RFID event: {E}, string: {string}")
        if self.state_class in [AuthorizedIdling, ProductionStageOngoing]:
            # if worker is logged in - log him out
            self.state.end_shift(string)
        elif self.state_class is AwaitLogin:
            # make a call to authorize the worker otherwise
            rfid_card_id: str = str(string)
            self.state.start_shift(rfid_card_id)

    def handle_barcode_event(self, barcode_string: str, additional_info: tp.Optional[AddInfo] = None) -> None:
        """Barcode event handling"""
        logger.debug(f"Handling barcode event. EAN: {barcode_string}, additional_info: {additional_info or 'is empty'}")

        # sequence to do if a worker is authorized but there's no ongoing operation
        if self.state_class is AuthorizedIdling:

            # create a new unit from submodules
            if self.create_new_unit:
                logger.info(f"Handling QR Code event for {barcode_string}. Creating new unit in progress")

                # check if it's a valid QR code link and add it to buffer. Display error otherwise.
                if utils.is_a_barcode(barcode_string):
                    Display().render_view(Alerts.InvalidQrAlert)
                    Display().render_view(Alerts.ScanQrCodeAlert)
                    return
                else:
                    self.state.qr_buffer = barcode_string  # type: ignore

                # check if buffer has enough links in it and create the unit. Display prompt message otherwise.
                if self.state.buffer_ready:
                    qr_links = self.state.qr_buffer
                    logger.info(f"Creating new unit featuring modules {qr_links}")
                    unit_internal_id, module_passports = self.state.create_unit_from_modules(qr_links)
                    self.state.start_operation_on_existing_unit(unit_internal_id, module_passports)
                else:
                    Display().render_view(Alerts.ScanNextModuleQr)
                    Display().render_view(Alerts.ScanQrCodeAlert)

            # start an operation on existing unit if it's a valid barcode
            elif utils.is_a_ean13_barcode(barcode_string):
                logger.info(f"Starting an operation for unit with int. id {barcode_string}")
                self.state.start_operation_on_existing_unit(barcode_string, additional_info)
            else:
                logger.warning(
                    f"'{barcode_string}' is not a EAN13 barcode and cannot be an internal unit ID. Cannot start operation."
                )
                Display().render_view(Alerts.InvalidBarcodeAlert)
                Display().render_view(Alerts.ScanBarcodeAlert)

        elif self.state_class is ProductionStageOngoing:
            logger.info(f"Ending an operation for unit with int. id {self.associated_unit_internal_id}")
            self.state.end_operation(additional_info)

        else:
            logger.error(f"Received input {barcode_string}. Ignoring event since no one is authorized.")
            Display().render_view(Alerts.AuthorizeFirstAlert)
            Display().render_view(Views.LoginScreen)
