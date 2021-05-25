import typing as tp
import sys
import yaml
import logging
import subprocess


def get_own_ip() -> str:
    """gets device's own ipv4 address on the local network"""

    command = "ip address | grep 192.168"
    result = subprocess.check_output(command, shell=True, text=True)
    ipv4 = ""

    for i in result.split(" "):
        if "192.168" in i:
            ipv4 = i.split("/")[0]
            break

    if ipv4:
        logging.info(f"Own ipv4 address is identified as {ipv4}")
    else:
        logging.error("Failed to parse own ipv4 address")

    return ipv4


def read_configuration(config_path: str = "config.yaml") -> tp.Dict[str, tp.Dict[str, tp.Any]]:
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
            logging.debug(f"Configuration dict: {content}")
            return config_f
    except Exception as e:
        logging.critical(f"Error while reading configuration file: \n{e}")
        sys.exit()
