import logging
import threading
import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime as dt
from math import floor
from time import sleep

from PIL import Image, ImageDraw, ImageFont

from Spoke import Spoke
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
        self._state._display = self

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
            logging.info(
                f"View changed from {self._latest_known_state.__class__.__name__} to {self.state}"
            )
            self._latest_known_state = self._state
            self._state.display()

        self._display_busy = False  # remove the flag

    @property
    def spoke_config(self):
        return self._spoke_config

    @property
    def associated_spoke(self):
        return self._associated_spoke

    @property
    def epd(self):
        return self._epd

    @property
    def associated_worker(self):
        return self._associated_worker

    @property
    def state(self):
        return self._state.__class__.__name__


class View(ABC):
    """
    abstract base class for all the views (states) to inherit from. 
    each view is responsible for an image drawn on the screen
    """

    def __init__(self) -> None:
        self._display: tp.Optional[Display] = None
        self._epd = self._display.epd

        # fonts
        self._font_s = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 11)
        self._font_m = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 20)
        self._font_l = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 36)

    def _save_image(self, image: Image) -> None:
        """saves image if specified in the config"""

        if self._display.spoke_config["developer"]["render_images"]:
            image.save(f"img/state-{self.__class__.__name__}-{str(dt.now()).split('.')[0]}.png")

    @abstractmethod
    def display(self) -> None:
        """a universal method that constructs the view and draws it onto a screen"""

        pass


class LoginScreen(View):
    """displays login screen"""

    def display(self) -> None:
        logging.info("Display login screen")

        # init image
        login_screen = Image.new("1", (self._epd.height, self._epd.width), 255)
        login_screen_draw = ImageDraw.Draw(login_screen)

        # draw the heading
        heading = "FEECC Spoke v1"
        w, h = login_screen_draw.textsize(heading, self._font_m)
        login_screen_draw.text((self._epd.width - w / 2, 5), heading, font=self._font_m, fill=0)

        # draw the RFID sign
        rfid_image = Image.open("img/rfid.png")
        rfid_image = rfid_image.resize((50, 50))
        block_start = 10 + h + 5
        login_screen.paste(rfid_image, (35, block_start))

        # draw the message
        message = "Приложите\nпропуск\nк сканеру"
        login_screen_draw.text((35 + 50 + 10, block_start), message, font=self._font_s, fill=0)

        # draw the footer
        footer = f"spoke no.{self._display.spoke_config['general']['spoke_num']}"
        ipv4 = self._display.associated_spoke.ipv4()

        if ipv4:
            footer += f". IPv4: {ipv4}"

        w, h = login_screen_draw.textsize(footer, self._font_s)
        login_screen_draw.text((self._epd.width - w / 2, block_start + 50 + 3), footer, font=self._font_s, fill=0)

        # display the image
        self._save_image(login_screen)
        self._epd.display(self._epd.getbuffer(login_screen))


class AuthorizationScreen(View):
    """displays authorization screen"""

    def display(self) -> None:
        logging.info("Display authorization screen")

        # init image
        auth_screen = Image.new("1", (self._epd.height, self._epd.width), 255)
        auth_screen_draw = ImageDraw.Draw(auth_screen)

        if not self._display.associated_worker.is_authorized:
            # display a message about failed authorization

            # draw the cross sign
            cross_image = Image.open("img/cross.png")
            img_h, img_w = (50, 50)
            cross_image = cross_image.resize((img_h, img_w))
            auth_screen.paste(cross_image, (20, floor((self._epd.width - img_h) / 2)))

            # draw the message
            message = "Авторизация\nне пройдена"
            txt_h, txt_w = auth_screen_draw.textsize(message, self._font_m)
            auth_screen_draw.text(
                (20 + img_w + 10, floor((self._epd.height - txt_h) / 2) - 15),
                message,
                font=self._font_m,
                fill=0
            )

            # display the image
            self._save_image(auth_screen)
            self._epd.display(self._epd.getbuffer(auth_screen))
            sleep(3)

            # since authorization failed switch back to login screen
            self._display.render_view(LoginScreen)
            return

        else:
            # authorization success
            # display a message about successful authorization

            # draw the tick sign
            tick_image = Image.open("img/tick.png")
            img_h, img_w = (50, 50)
            tick_image = tick_image.resize((img_h, img_w))
            auth_screen.paste(tick_image, (20, floor((self._epd.width - img_h) / 2)))

            try:
                worker_position: str = self._display.associated_worker.position
                worker_short_name: str = self._display.associated_worker.short_name()
                message = f"Авторизован\n{worker_position}\n{worker_short_name}"

                # draw the message
                auth_screen_draw.text((20 + img_w + 10, 30), message, font=self._font_s, fill=0)

            except KeyError:
                message = "Успешная\nавторизация"

                # draw the message
                auth_screen_draw.text((20 + img_w + 10, 30), message, font=self._font_m, fill=0)

            # display the image
            self._save_image(auth_screen)
            self._epd.display(self._epd.getbuffer(auth_screen))
            sleep(3)

            # switch to barcode await screen
            self._display.render_view(AwaitInputScreen)


class AwaitInputScreen(View):
    """displays the barcode scan prompt"""

    def display(self) -> None:
        logging.info(f"Display barcode scan prompt")

        image = Image.new("1", (self._epd.height, self._epd.width), 255)
        message = "Сканируйте\nштрихкод"

        footer = f"Авторизован {self._display.associated_worker.short_name()}"
        logging.debug(f"Footer: {footer}")

        image_draw = ImageDraw.Draw(image)
        barcode_image = Image.open("img/barcode.png")

        # draw the barcode icon
        logging.debug(f"Drawing the barcode icon")
        img_h, img_w = (50, 50)
        barcode_image = barcode_image.resize((img_h, img_w))
        image.paste(barcode_image, (10, 10))

        # draw the text
        logging.debug(f"Drawing the main message")
        image_draw.text((10 + img_w + 10, 10), message, font=self._font_m, fill=0)

        # draw the footer
        logging.debug(f"Drawing the footer")
        footer_h, footer_w = image_draw.textsize(footer, font=self._font_s)
        image_draw.text((floor((self._epd.width - footer_w) / 2), 10 + img_h + 10), footer, font=self._font_s, fill=0)

        # draw the image
        logging.info(f"Drawing the await screen image")
        self._save_image(image)
        self._epd.display(self._epd.getbuffer(image))


class OngoingOperationScreen(View):
    """Displays the assembly timer"""

    def display(self) -> None:
        logging.info("Display assembly timer")
        time_image = Image.new("1", (self._epd.height, self._epd.width), 255)
        time_draw = ImageDraw.Draw(time_image)

        message = "ИДЕТ ЗАПИСЬ"
        w, h = time_draw.textsize(message, self._font_m)
        time_draw.text((self._epd.width - w / 2, 10), message, font=self._font_m, fill=0)

        message = "Для завершения сканировать\nштрихкод еще раз"
        w, h = time_draw.textsize(message, self._font_s)
        time_draw.text((self._epd.width - w / 2, 67), message, font=self._font_s, fill=0, align="center")
        start_time = dt.now()

        while True:
            timer_delta = dt.now() - start_time
            timer = dt.utcfromtimestamp(timer_delta.total_seconds())
            message = timer.strftime("%H:%M:%S")

            w, h = time_draw.textsize(message, self._font_l)
            nw_w = floor(self._epd.width - w / 2)
            time_draw.rectangle((nw_w, 30, nw_w + w, 30 + h), fill=255)
            time_draw.text(
                (nw_w, 30), message, font=self._font_l, fill=0
            )
            new_image = time_image.crop([nw_w, 30, nw_w + w, 30 + h])
            time_image.paste(new_image, (nw_w, 30))
            self._epd.DisplayPartial(self._epd.getbuffer(time_image))


class BlankScreen(View):
    """used to clear the screen before and after usage"""

    def display(self) -> None:
        logging.info("Clearing the screen")
        self._epd.init()
        self._epd.Clear(0x00)  # fill with black to remove stuck pixels
        self._epd.Clear(0xFF)  # fill with white
        logging.debug("Finished clearing the screen")
