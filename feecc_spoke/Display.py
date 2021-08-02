import logging
import threading
import typing as tp
from time import sleep, time

from .Employee import Employee
from .Spoke import Spoke
from .ViewBase import View
from .Views import BlankScreen

try:
    from .waveshare_epd import epd2in13d, epdconfig
except Exception as E:
    logging.error(f"Couldn't import EPD library: {E}")


# This set of classes implements the "State" pattern
# refer to https://refactoring.guru/ru/design-patterns/state
# for more information on it's principles


class Display:
    """the context class"""

    def __init__(self, associated_worker: Employee, associated_spoke: Spoke) -> None:
        self._state: tp.Optional[View] = None
        self.associated_worker: Employee = associated_worker
        self.associated_spoke: Spoke = associated_spoke
        self.spoke_config: tp.Dict[str, tp.Dict[str, tp.Any]] = self.associated_spoke.config
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
    def headless_mode(self) -> bool:
        return any((self.epd is None, self.spoke_config["screen"]["enforce_headless"]))

    @property
    def state(self) -> str:
        return self._state.__class__.__name__

    @property
    def current_view(self) -> tp.Optional[tp.Type[View]]:

        if self._state is None:
            return None

        return self._state.__class__

    def render_view(self, new_state: tp.Type[View]) -> None:
        """handle display state change in a separate thread"""
        if self.headless_mode:
            return

        previous_state: str = self.state
        self._state = new_state(self)
        logging.info(f"Display: rendering view {self.state}")

        # wait for the ongoing operation to finish to avoid overwhelming the display
        if self._display_busy:
            logging.debug(f"Display busy. Waiting to draw {self.state}")
            # drop pending View if it is the same one which is on the display now
            if self.state == previous_state:
                msg = f"Pending View ({self.state}) matches the current View. View render dropped."
                logging.info(msg)
                return
            # wait before drawing otherwise
            else:
                while self._display_busy:
                    sleep(0.5)

        self._display_thread = threading.Thread(target=self._handle_state_change)
        self._display_thread.start()  # handle the state change in a separate thread

    def end_session(self) -> None:
        """clear the screen if execution is interrupted or script exits"""
        if self.headless_mode:
            return

        self.render_view(BlankScreen)
        epdconfig.module_exit()

        if self._display_thread:
            self._display_thread.join(timeout=1)

    def _handle_state_change(self) -> None:
        """handle state changing and change the output accordingly"""
        self._display_busy = True  # raise the flag
        logging.info(f"View changed to {self.state}")

        if self._state:
            state_name: str = self.state
            start_time: float = time()
            self._state.display()
            end_time: float = time()
            logging.debug(f"View '{state_name}' displayed in {end_time - start_time} s.")

        self._display_busy = False  # remove the flag
