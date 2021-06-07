import logging
import threading
import typing as tp
from time import sleep

from Spoke import Spoke
from Views import BlankScreen, View
from Worker import Worker
from waveshare_epd import epd2in13d

# Set output log level
logging.basicConfig(level=logging.DEBUG)


# This set of classes implements the "State" pattern
# refer to https://refactoring.guru/ru/design-patterns/state
# for more information on it's principles


class Display:
    """the context class"""

    def __init__(self, associated_worker: Worker, associated_spoke: Spoke) -> None:
        self._state: tp.Optional[View] = None  # a View type of object which is responsible for the state
        self._latest_known_state: tp.Optional[View] = None
        self._associated_worker: Worker = associated_worker
        self._associated_spoke: Spoke = associated_spoke
        self._spoke_config: tp.Dict[str, tp.Dict[str, tp.Any]] = self._associated_spoke.config
        self._epd = epd2in13d.EPD()

        # thread for the display to run in
        self._display_thread: tp.Optional[threading.Thread] = None
        self._display_busy: bool = False

        # clear the screen at the first start in case it has leftover images on it
        self.render_view(BlankScreen)

    def render_view(self, new_state) -> None:
        """
        handle display state change in a separate thread
        :param new_state: object of type View to be displayed
        :return:
        """

        self._state = new_state
        self._state.context = self

        # wait for the ongoing operation to finish to avoid overwhelming the display
        while self._display_busy:
            sleep(0.5)

        self._display_thread = threading.Thread(target=self._handle_state_change)
        self._display_thread.start()  # handle the state change in a separate thread

    def end_session(self) -> None:
        """clear the screen if execution is interrupted or script exits"""

        self.render_view(BlankScreen)
        epd2in13d.epdconfig.module_exit()
        self._display_thread.join(timeout=1)

    def _handle_state_change(self) -> None:
        """handle state changing and change the output accordingly"""

        self._display_busy = True  # raise the flag

        while self._state != self._latest_known_state:
            logging.info(f"View changed from {self._latest_known_state.__class__.__name__} to {self.state}")
            self._latest_known_state = self._state
            self._state.display()

        self._display_busy = False  # remove the flag

    @property
    def spoke_config(self) -> tp.Dict[str, tp.Dict[str, tp.Any]]:
        return self._spoke_config

    @property
    def associated_spoke(self) -> Spoke:
        return self._associated_spoke

    @property
    def epd(self) -> epd2in13d.EPD:
        return self._epd

    @property
    def associated_worker(self) -> Worker:
        return self._associated_worker

    @property
    def state(self) -> str:
        return self._state.__class__.__name__
