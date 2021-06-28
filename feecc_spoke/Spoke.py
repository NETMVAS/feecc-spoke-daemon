import logging
import subprocess
import sys
import typing as tp

import requests
import yaml


class Spoke:
    """stores device's status and operational data"""

    def __init__(self) -> None:
        self.config: tp.Dict[str, tp.Dict[str, tp.Any]] = self._read_configuration()
        self.recording_in_progress: bool = False
        self.associated_unit_internal_id: str = ""

    @property
    def number(self) -> int:
        workbench_no: int = self.config["general"]["workbench_no"]
        return workbench_no

    @property
    def hub_url(self) -> str:
        hub_socket: str = self.config["endpoints"]["hub_socket"]
        return hub_socket

    def invert_rec_flag(self) -> None:
        self.recording_in_progress = not self.recording_in_progress

    @staticmethod
    def ipv4() -> str:
        """gets device's own ipv4 address on the local network"""

        command = "ip address | grep 192.168"
        output: str = subprocess.check_output(command, shell=True, text=True)
        ipv4 = ""

        for word in output.split():
            if "192.168" in word:
                ipv4 = word.split("/")[0]
                break

        if ipv4:
            logging.info(f"Own ipv4 address is identified as {ipv4}")
        else:
            logging.error("Failed to parse own ipv4 address")

        return ipv4

    @staticmethod
    def _read_configuration(config_path: str = "config.yaml") -> tp.Dict[str, tp.Dict[str, tp.Any]]:
        """
        :return: dictionary containing all the configurations
        :rtype: dict

        Reading config, containing all the required data, such as filepath,
        robonomics parameters (remote wss, seed),
        camera parameters (ip, login, password, port), etc
        """

        logging.debug(f"Looking for config at {config_path}")

        try:
            with open(config_path) as f:
                content = f.read()
                config_f: tp.Dict[str, tp.Dict[str, tp.Any]] = yaml.load(
                    content, Loader=yaml.FullLoader
                )
                logging.debug(f"Configuration dict: {config_f}")
                return config_f
        except Exception as e:
            logging.critical(f"Error while reading configuration file: \n{e}")
            sys.exit()

    def identify_sender(self, sender_device_name: str) -> str:
        """identify, which device the input is coming from and if it is known return it's role"""

        known_hid_devices: tp.Dict[str, str] = self.config["known_hid_devices"]
        sender = ""  # name of the sender device

        for sender_name, device_name in known_hid_devices.items():
            if device_name == sender_device_name:
                sender = sender_name
                break

        return sender

    def end_recording(self) -> None:
        """ends recording if there is any"""

        if self.recording_in_progress:
            if not self.config["developer"]["disable_barcode_validation"]:
                url = f"{self.hub_url}/api/unit/{self.associated_unit_internal_id}/end"
                payload = {"workbench_no": self.number, "additional_info": {}}

                requests.post(url=url, json=payload)

            self.invert_rec_flag()
