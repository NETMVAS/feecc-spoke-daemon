import os
import re
import subprocess
import sys
import typing as tp

import yaml
from loguru import logger

from .Types import Config


def get_config(config_path: str = "config.yaml") -> Config:
    """load up config file"""
    if not os.path.exists(config_path):
        logger.critical(f"Configuration file {config_path} doesn't exist. Exiting.")
        sys.exit()

    with open(config_path) as f:
        content = f.read()
        config_f: Config = yaml.load(content, Loader=yaml.SafeLoader)
        logger.debug(f"Configuration dict: {config_f}")
        return config_f


def get_interface_ipv4() -> tp.Optional[str]:
    """gets device's own ipv4 address on the local network"""
    try:
        command = "ip address | grep 192.168"
        output: str = subprocess.check_output(command, shell=True, text=True)
        ip_addresses: tp.List[str] = re.findall("192.168.\d+.\d+", output)
        return ip_addresses[0] if ip_addresses else None
    except Exception as E:
        logger.error(f"An error occurred while retrieving own ipv4: {E}")
        return None


def is_a_barcode(string: str) -> bool:
    """define if the barcode scanner input is barcode"""
    return bool(re.fullmatch("\d+", string))


def is_a_ean13_barcode(string: str) -> bool:
    """define if the barcode scanner input is a valid EAN13 barcode"""
    return bool(re.fullmatch("\d{13}", string))
