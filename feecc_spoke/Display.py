import typing as tp
from collections import deque
from threading import Thread
from time import time

from loguru import logger

from Types import Config
from .Employee import Employee
from .Spoke import Spoke
from .ViewBase import View
from .Views import BlankScreen
from ._Singleton import SingletonMeta

try:
    from .waveshare_epd import epd2in13d, epdconfig
except Exception as E:
    logger.error(f"Couldn't import EPD library: {E}")


class Display(metaclass=SingletonMeta):
    """the context class. handles hardware display operation and view management"""

    def __init__(self) -> None:
        self.associated_worker: Employee = Employee()
        self.associated_spoke: Spoke = Spoke()
        self.spoke_config: Config = self.associated_spoke.config
        self.epd: tp.Optional[epd2in13d.EPD] = None

        try:
            self.epd = epd2in13d.EPD()
        except Exception as e:
            logger.warning("E-ink display initialization failed. Fallback to headless mode.")
            logger.debug(e)

        self.current_view: tp.Optional[View] = None
        self._view_queue: tp.Deque[tp.Type[View]] = deque()
        self._display_thread: tp.Optional[Thread] = None

        # clear the screen at the first start in case it has leftover images on it
        self.render_view(BlankScreen)

    @property
    def _headless_mode(self) -> bool:
        return any((self.epd is None, self.spoke_config["screen"]["enforce_headless"]))

    @property
    def _display_busy(self) -> bool:
        return self._display_thread is not None and self._display_thread.is_alive()

    def end_session(self) -> None:
        """clear the screen if execution is interrupted or script exits"""
        if not self._headless_mode:
            self.render_view(BlankScreen)
            epdconfig.module_exit()
            if self._display_thread is not None:
                self._display_thread.join()

    def render_view(self, view: tp.Type[View]) -> None:
        """handle rendering a view in a separate thread"""
        # drop render task if in headless mode
        if self._headless_mode:
            return
        # put the view into queue for rendering if it it is not duplicate
        if self._view_queue and self._view_queue[-1] == view:
            logger.debug(f"View {view.__name__} is already pending rendering. Dropping task.")
            return
        elif self.current_view.__class__ == view and not self._view_queue:
            logger.debug(f"View {view.__name__} is currently on the display. Dropping task.")
            return
        else:
            logger.debug(f"View {view.__name__} staged for rendering")
            self._view_queue.append(view)
        # only start a new thread if there's no ongoing rendering process
        if not self._display_busy:
            self._display_thread = Thread(target=self._render_view_queue)
            self._display_thread.start()
            logger.debug(f"New queue rendering thread started: {repr(self._display_thread)}")

    def _render_view_queue(self) -> None:
        """render all pending views one by one"""
        while self._view_queue:
            pending_view: tp.Type[View] = self._view_queue.popleft()
            view: View = pending_view(self)
            self.current_view = view
            logger.info(f"Rendering view {view.name}")
            start_time: float = time()
            view.display()
            end_time: float = time()
            logger.debug(f"View '{view.name}' displayed in {round(end_time-start_time, 3)} s.")
