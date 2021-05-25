from dataclasses import dataclass
import logging


@dataclass
class Worker:
    """stores data about the worker"""

    is_authorized: bool = False
    full_name: str = "Иванов Иван Иванович"
    position: str = "Младший инженер"

    def log_in(self) -> None:
        """end working session and log out the worker"""

        logging.info(f"{self.position} {self.short_name()} logged in")
        self.is_authorized = True

    def log_out(self) -> None:
        """end working session and log out the worker"""

        logging.info(f"{self.position} {self.short_name()} logged out")
        self.full_name = ""
        self.position = ""
        self.is_authorized = False

    def short_name(self) -> str:
        """
        shortens name like so:
        Ivanov Ivan Ivanovich -> Ivanov I. I.
        """

        full_name: str = self.full_name
        name = full_name.split(" ")
        short_name = [name[0]]
        for part in name[1:]:
            part = part[0] + "."
            short_name.append(part)

        return " ".join(short_name)
