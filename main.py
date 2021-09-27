import atexit
import typing as tp
from time import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from feecc_spoke.Display import Display
from feecc_spoke.Employee import Employee
from feecc_spoke.Exceptions import StateForbiddenError
from feecc_spoke.Spoke import Spoke
from feecc_spoke.Types import RequestPayload
from feecc_spoke.models import BaseEvent

logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

api = FastAPI()

api.add_middleware(CORSMiddleware, allow_origins=["*"])


@atexit.register
def end_session() -> None:
    """log out the worker, clear the display, release SPI and join the thread before exiting"""
    logger.info("SIGTERM handling started")
    if Employee().is_authorized:
        logger.info("Employee logged in. Logging out before exiting.")
        Spoke().state.end_shift(Employee().rfid_card_id)
    Display().end_session()
    logger.info("SIGTERM handling finished")


@api.post("/api/hid_event")
def handle_hid_event(event: BaseEvent) -> RequestPayload:
    """Parse the event dict JSON"""
    logger.debug(f"Received event dict:\n{event.json()}")
    # handle the event in accord with it's source
    sender: tp.Optional[str] = Spoke().identify_sender(event.name)
    string: str = event.string

    if sender is not None:
        Spoke().hid_buffer = string
        Spoke().hid_buffer_added_on = int(time())

    try:
        if sender == "rfid_reader":
            Spoke().handle_rfid_event(string)
        elif sender == "barcode_reader":
            Spoke().handle_barcode_event(string)
        else:
            message: str = "Sender of the event dict is not mentioned in the config. Can't handle the request."
            logger.error(message)
            return {"status": False, "comment": message}

        return {"status": True, "comment": "Hid event has been handled as expected"}

    except StateForbiddenError as E:
        return {"status": False, "comment": f"operation is forbidden by the state: {E}"}


@api.get("/api/hid_buffer")
def get_latest_buffer_entry() -> RequestPayload:
    """get latest buffer entry"""
    return {
        "status": True,
        "comment": "Retrieved HID buffer",
        "buffer": Spoke().hid_buffer,
        "added_on": Spoke().hid_buffer_added_on,
    }


if __name__ == "__main__":
    Display()
    logger.info("Syncing login status")
    Spoke().sync_login_status()
    logger.info("Starting server")
    server_ip: str = Spoke().config["api"]["server_ip"]
    server_port: int = int(Spoke().config["api"]["server_port"])
    uvicorn.run("app:api", host=server_ip, port=server_port)
