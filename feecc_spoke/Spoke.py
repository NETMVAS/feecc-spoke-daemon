from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import typing as tp
from random import randint

import requests
import yaml
from loguru import logger

from . import Alerts, Views
from .Display import Display
from .Employee import Employee
from .Exceptions import BackendUnreachableError
from .State import AuthorizedIdling, AwaitLogin, ProductionStageOngoing, State
from .Types import AddInfo, Config, RequestPayload
from ._Singleton import SingletonMeta


class Spoke(metaclass=SingletonMeta):
    """stores device's status and operational data"""

    def __init__(self) -> None:
        self.config: Config = self._get_config()
        self.associated_unit_internal_id: tp.Optional[str] = None
        self.state: State = AwaitLogin(self)
        self._state_thread_list: tp.List[threading.Thread] = []

    @property
    def operation_ongoing(self) -> bool:
        return self.associated_unit_internal_id is not None

    @property
    def number(self) -> int:
        workbench_no: int = int(self.config["general"]["workbench_no"])
        return workbench_no

    @property
    def hub_url(self) -> str:
        hub_socket: str = str(self.config["endpoints"]["hub_socket"])
        return hub_socket

    @property
    def ipv4(self) -> tp.Optional[str]:
        """gets device's own ipv4 address on the local network"""
        try:
            command = "ip address | grep 192.168"
            output: str = subprocess.check_output(command, shell=True, text=True)
            ip_addresses: tp.List[str] = re.findall("192.168.\d+.\d+", output)
            return ip_addresses[0] if ip_addresses else None
        except Exception as E:
            logger.error(f"An error occurred while retrieving own ipv4: {E}")
            return None

    @property
    def workbench_status(self) -> RequestPayload:
        url: str = f"{self.hub_url}/api/workbench/{self.number}/status"
        try:
            workbench_status: RequestPayload = requests.get(url, timeout=1).json()
            return workbench_status
        except Exception as E:
            message = f"Backend unreachable: {E}"
            logger.error(message)
            raise BackendUnreachableError(message)

    @property
    def disable_id_validation(self) -> bool:
        return bool(self.config["developer"]["disable_id_validation"])

    @property
    def disable_barcode_validation(self) -> bool:
        return bool(self.config["developer"]["disable_barcode_validation"])

    @staticmethod
    def _get_config(config_path: str = "config.yaml") -> Config:
        """load up config file"""
        if not os.path.exists(config_path):
            logger.critical(f"Configuration file {config_path} doesn't exist. Exiting.")
            sys.exit()

        with open(config_path) as f:
            content = f.read()
            config_f: Config = yaml.load(content, Loader=yaml.SafeLoader)
            logger.debug(f"Configuration dict: {config_f}")
            return config_f

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
            Display().render_view(Alerts.ScanBarcodeAlert)
        else:
            Display().render_view(Views.LoginScreen)

    def identify_sender(self, sender_device_name: str) -> str:
        """identify, which device the input is coming from and if it is known return it's role"""
        known_hid_devices: tp.Dict[str, str] = self.config["known_hid_devices"]
        sender = ""  # name of the sender device

        for sender_name, device_name in known_hid_devices.items():
            if device_name == sender_device_name:
                sender = sender_name
                break

        return sender

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

    def handle_rfid_event(self, event_dict: RequestPayload) -> None:
        """RFID event handling"""
        # resolve sync conflicts
        try:
            workbench_status: RequestPayload = self.workbench_status
            if not Employee().is_authorized == workbench_status["employee_logged_in"]:
                self.sync_login_status()
        except BackendUnreachableError as E:
            logger.error(f"Failed to handle RFID event: {E}, event: {event_dict}")
            pass

        if self.state_class in [AuthorizedIdling, ProductionStageOngoing]:
            # if worker is logged in - log him out
            self.state.end_shift(event_dict["string"])
        elif self.state_class is AwaitLogin:
            # make a call to authorize the worker otherwise
            rfid_card_id: str = str(event_dict["string"])
            self.state.start_shift(rfid_card_id)

    def handle_barcode_event(self, barcode_string: str, additional_info: tp.Optional[AddInfo] = None) -> None:
        """Barcode event handling"""
        logger.debug(f"Handling barcode event. EAN: {barcode_string}, additional_info: {additional_info or 'is empty'}")

        if self.state_class is AuthorizedIdling:
            if self.config["general"]["create_new_unit"]:
                logger.info(f"Handling QR Code event for {barcode_string}. Creating new unit in progress")
                if self.state.buffer_ready:
                    qr_links = self.state.qr_buffer
                    logger.info(f"Creating new unit featuring modules {qr_links}")
                    self.state.create_unit_from_modules(qr_links)
                elif self._is_a_barcode(barcode_string):
                    Display().render_view(Alerts.InvalidQrAlert)
                    Display().render_view(Alerts.ScanBarcodeAlert)
                else:
                    self.state.qr_buffer = barcode_string  # type: ignore

            else:
                logger.info(f"Starting an operation for unit with int. id {barcode_string}")
                self.state.start_operation_on_existing_unit(barcode_string, additional_info)
        elif self.state_class is ProductionStageOngoing:
            logger.info(f"Ending an operation for unit with int. id {barcode_string}")
            self.state.end_operation(barcode_string, additional_info)
        else:
            logger.error(
                f"Nothing to do for unit with int. id {barcode_string}. Ignoring event since no one is authorized."
            )
            Display().render_view(Alerts.AuthorizeFirstAlert)
            Display().render_view(Views.LoginScreen)

    @staticmethod
    def _is_a_barcode(string: str) -> bool:
        """define if the barcode scanner input is a valid EAN13 barcode"""
        return bool(re.fullmatch("\d{13}", string))
