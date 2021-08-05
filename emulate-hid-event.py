from pprint import pprint
from sys import argv

import requests

SERVER_API_ADDRESS = "http://127.0.0.1:8080/api"


def rfid_event(junk_data: bool = False) -> None:
    """emulate rfid scanner event"""
    string: str = "00000000" if junk_data else "1111111111"
    sender: str = "Sycreader RFID Technology Co., Ltd SYC ID&IC USB Reader"
    generic_hid_event(sender, string)


def barcode_event(junk_data: bool = False) -> None:
    """emulate barcode scanner event"""
    string: str = "00000000" if junk_data else "11111111111111111111111"
    sender: str = "HENEX 2D Barcode Scanner"
    generic_hid_event(sender, string)


def generic_hid_event(sender: str, payload: str) -> None:
    """send a hid request with provided payload"""
    try:
        response = requests.post(
            SERVER_API_ADDRESS + "/hid_event",
            json={"string": payload, "name": sender},
        )
    except Exception as e:
        print(f"Server {SERVER_API_ADDRESS} unreachable: {e}")
        return

    pprint(response.json())


if __name__ == "__main__":
    options: str = """
    Emulator options (entered as CLI argument or at input"):
    [ 0 ] - valid RFID event
    [ 1 ] - junk RFID event
    [ 2 ] - valid barcode event
    [ 3 ] - junk barcode event
    """
    print(options)
    option: str = argv[1] if len(argv) >= 2 else input()
    if option == "0":
        rfid_event(junk_data=False)
    elif option == "1":
        rfid_event(junk_data=True)
    elif option == "2":
        barcode_event(junk_data=False)
    elif option == "3":
        barcode_event(junk_data=True)
    else:
        print("Invalid option")
