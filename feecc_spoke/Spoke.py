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

from .Exceptions import BackendUnreachableError
from .Types import Config, RequestPayload
from ._Singleton import SingletonMeta

if tp.TYPE_CHECKING:
    from .State import State


class Spoke(metaclass=SingletonMeta):
    """stores device's status and operational data"""

    def __init__(self) -> None:
        from .State import AwaitLogin  # moved to avoid circular import issue

        self.config: Config = self._get_config()
        self.associated_unit_internal_id: tp.Optional[str] = None
        self.state: State = AwaitLogin()
        self.previous_state: tp.Optional[tp.Type[State]] = None
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
        self.previous_state = self.state_class
        self.state = state()
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
