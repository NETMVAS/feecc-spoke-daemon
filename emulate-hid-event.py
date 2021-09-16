#!.venv/bin/python

import typer
import requests

app = typer.Typer()
SERVER_API_ADDRESS = "http://127.0.0.1:8080/api"


@app.command()
def rfid(string: str = "1111111111", sender: str = "Sycreader RFID Technology Co., Ltd SYC ID&IC USB Reader") -> None:
    """emulate rfid scanner event"""
    generic_hid_event(sender, string)


@app.command()
def barcode(string: str = "11111111111111111111111", sender: str = "HENEX 2D Barcode Scanner") -> None:
    """emulate barcode scanner event"""
    generic_hid_event(sender, string)


@app.command()
def generic_hid_event(sender: str, payload: str) -> None:
    """send a hid request with provided payload"""
    try:
        endpoint = SERVER_API_ADDRESS + "/hid_event"
        typer.echo(f"\nSender: {sender}\nPayload: {payload}\nEndpoint: {endpoint}\n")
        response = requests.post(
            endpoint,
            json={"string": payload, "name": sender},
        )
    except Exception as E:
        typer.echo(f"Server {SERVER_API_ADDRESS} unreachable: {E}", err=True)
        return

    typer.echo(response.json())


if __name__ == "__main__":
    app()
