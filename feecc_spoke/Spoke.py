import logging
import os
import re
import subprocess
import sys
import typing as tp

import requests
import yaml

from exceptions import BackendUnreachableError
from Types import Config, RequestPayload


class Spoke:
    """stores device's status and operational data"""

    def __init__(self) -> None:
        self.config: Config = self._get_config()
        self.associated_unit_internal_id: tp.Optional[str] = None

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
        command = "ip address | grep 192.168"
        output: str = subprocess.check_output(command, shell=True, text=True)
        ip_addresses: tp.List[str] = re.findall("192.168.\d+.\d+", output)
        return ip_addresses[0] if ip_addresses else None

    @property
    def workbench_status(self) -> RequestPayload:
        url: str = f"{self.hub_url}/api/workbench/{self.number}/status"
        try:
            workbench_status: RequestPayload = requests.get(url, timeout=1).json()
            return workbench_status
        except Exception as E:
            logging.error(f"Backend unreachable: {E}")
            raise BackendUnreachableError

    @staticmethod
    def _get_config(config_path: str = "config.yaml") -> Config:
        """load up config file"""
        if not os.path.exists(config_path):
            logging.critical(f"Configuration file {config_path} doesn't exist. Exiting.")
            sys.exit()

        with open(config_path) as f:
            content = f.read()
            config_f: Config = yaml.load(content, Loader=yaml.SafeLoader)
            logging.debug(f"Configuration dict: {config_f}")
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
