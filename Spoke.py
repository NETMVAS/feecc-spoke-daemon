import typing as tp
import sys
import yaml
import logging
import subprocess
import requests


class Spoke:
    """stores device's status and operational data"""

    def __init__(self) -> None:
        self.config: tp.Dict[str, tp.Dict[str, tp.Any]] = self._read_configuration()
        self.recording_in_progress: bool = False
        self.latest_barcode_payload: tp.Optional[tp.Any] = None

    def submit_barcode(self, payload: tp.Dict[str, tp.Any]) -> tp.Dict[str, tp.Any]:
        """
        submit barcode event to the hub by sending an API call
        :param payload: dict to send in the request
        :return: response dict from the API
        """
        response = requests.post(
            url=f'{self.config["endpoints"]["hub_socket"]}/api/passport',
            json=payload
        )

        response_data: tp.Dict[str, tp.Any] = response.json()

        return response_data

    def submit_rfid(self, payload: tp.Dict[str, tp.Any]) -> tp.Dict[str, str]:
        """
        submit RFID event to the hub by sending an API call
        :param payload: dict to send in the request
        :return: response dict from the API
        """

        response = requests.post(
            url=f'{self.config["endpoints"]["hub_socket"]}/api/validator',
            json=payload
        )

        response_data: tp.Dict[str, str] = response.json()

        return response_data

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

        Reading config, containing all the required data, such as filepath, robonomics parameters (remote wss, seed),
        camera parameters (ip, login, password, port), etc
        """

        logging.debug(f"Looking for config at {config_path}")

        try:
            with open(config_path) as f:
                content = f.read()
                config_f: tp.Dict[str, tp.Dict[str, tp.Any]] = yaml.load(content, Loader=yaml.FullLoader)
                logging.debug(f"Configuration dict: {config_f}")
                return config_f
        except Exception as e:
            logging.critical(f"Error while reading configuration file: \n{e}")
            sys.exit()

    def identify_sender(self, sender_device_name: str) -> str:
        """identify, from which device the input is coming from and if it is known return it's role"""

        known_hid_devices: tp.Dict[str, str] = self.config["known_hid_devices"]
        sender = ""  # name of the sender device

        for sender_name, device_name in known_hid_devices.items():
            if device_name == sender_device_name:
                sender = sender_name
                break

        return sender

    def end_recording(self) -> None:
        """ends recording if there is any"""

        payload = self.latest_barcode_payload
        self.submit_barcode(payload)
        self.recording_in_progress = False
