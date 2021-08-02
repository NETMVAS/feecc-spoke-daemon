import logging
import threading
import typing as tp
from time import sleep, time

from Types import Config
from .Employee import Employee
from .Spoke import Spoke
from .ViewBase import View
from .Views import BlankScreen

try:
    from .waveshare_epd import epd2in13d, epdconfig
except Exception as E:
    logging.error(f"Couldn't import EPD library: {E}")


class Display:
    """the context class. handles hardware display operation and view management"""

    def __init__(self, associated_worker: Employee, associated_spoke: Spoke) -> None:
        self._view: tp.Optional[View] = None
        self.associated_worker: Employee = associated_worker
        self.associated_spoke: Spoke = associated_spoke
        self.spoke_config: Config = self.associated_spoke.config
        self.epd: tp.Optional[epd2in13d.EPD] = None

        try:
            self.epd = epd2in13d.EPD()
        except Exception as e:
            logging.warning("E-ink display initialization failed. Fallback to headless mode.")
            logging.debug(e)

        # thread for the display to run in
        self._display_thread: tp.Optional[threading.Thread] = None
        self._display_busy: bool = False

        # clear the screen at the first start in case it has leftover images on it
        self.render_view(BlankScreen)

    @property
    def _headless_mode(self) -> bool:
        return any((self.epd is None, self.spoke_config["screen"]["enforce_headless"]))

    @property
    def view_name(self) -> str:
        return self._view.__class__.__name__

    @property
    def current_view(self) -> tp.Optional[tp.Type[View]]:
        return None if self._view is None else self._view.__class__

    def end_session(self) -> None:
        """clear the screen if execution is interrupted or script exits"""
        if self._headless_mode:
            return

        self.render_view(BlankScreen)
        epdconfig.module_exit()

        if self._display_thread:
            self._display_thread.join(timeout=1)

    def render_view(self, new_state: tp.Type[View]) -> None:
        """handle display state change in a separate thread"""
        if self._headless_mode:
            return

        previous_state: str = self.view_name
        self._view = new_state(self)
        logging.info(f"Display: rendering view {self.view_name}")

        # wait for the ongoing operation to finish to avoid overwhelming the display
        if self._display_busy:
            logging.debug(f"Display busy. Waiting to draw {self.view_name}")
            # drop pending View if it is the same one which is on the display now
            if self.view_name == previous_state:
                msg = f"Pending View ({self.view_name}) matches the current View. View render dropped."
                logging.info(msg)
                return
            # wait before drawing otherwise
            else:
                while self._display_busy:
                    sleep(0.5)

        self._display_thread = threading.Thread(target=self._handle_state_change)
        self._display_thread.start()  # handle the state change in a separate thread

    def _handle_state_change(self) -> None:
        """handle state changing and change the output accordingly"""
        self._display_busy = True  # raise the flag
        logging.info(f"View changed to {self.view_name}")

        if self._view:
            state_name: str = self.view_name
            start_time: float = time()
            self._view.display()
            end_time: float = time()
            logging.debug(f"View '{state_name}' displayed in {end_time - start_time} s.")

        self._display_busy = False  # remove the flag
