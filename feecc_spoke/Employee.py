import typing as tp
from dataclasses import dataclass

from loguru import logger


@dataclass
class Employee:
    """stores data about the worker"""

    is_authorized: bool = False
    full_name: str = ""
    position: str = ""
    rfid_card_id: str = ""

    @property
    def short_name(self) -> str:
        """
        shortens name like so:
        Ivanov Ivan Ivanovich -> Ivanov I. I.
        """
        full_name: str = self.full_name
        try:
            name = full_name.split()
            short_name: tp.List[str] = [name[0]]
            for part in name[1:]:
                part = part[0] + "."
                short_name.append(part)
            return " ".join(short_name)
        except Exception as E:
            logger.debug(f"Short name generation failed for the full name '{full_name}'. E: {E}")
            return full_name

    def log_in(self, position: str, full_name: str, card_id: str) -> None:
        """end working session and log out the worker"""
        self.full_name = full_name
        self.position = position
        self.rfid_card_id = card_id
        self.is_authorized = True
        logger.info(f"{self.position} {self.short_name} logged in")

    def log_out(self) -> None:
        """end working session and log out the worker"""
        self.full_name = ""
        self.position = ""
        self.is_authorized = False
        logger.info(f"{self.position} {self.short_name} logged out")
