from __future__ import annotations

import logging
import os
import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime as dt
from math import floor
from time import sleep

from PIL import Image, ImageDraw, ImageFont

if tp.TYPE_CHECKING:
    from .waveshare_epd import epd2in13d
    from PIL.ImageFont import FreeTypeFont
    from Display import Display


# a View is an image unit - one drawable medium,
# which can be displayed on the screen by executing
# the display method of the View subclass object

# font related constants
FONT_PATH: str = "feecc_spoke/fonts/helvetica-cyrillic-bold.ttf"
SMALL_FONT_SIZE: int = 11
MEDIUM_FONT_SIZE: int = 20
LARGE_FONT_SIZE: int = 36


class View(ABC):
    """
    abstract base class for all the views (states) to inherit from.
    each view is responsible for an image drawn on the screen
    """

    def __init__(self, context: Display) -> None:
        # associated display parameters
        self._display: Display = context
        self._epd: epd2in13d.EPD = self._display.epd
        self._height: int = self._epd.height
        self._width: int = self._epd.width
        logging.debug(f"{self.name} context set as {self._display}")

        # fonts
        logging.debug(f"Using font {os.path.basename(FONT_PATH)}")
        self._font_s: FreeTypeFont = ImageFont.truetype(FONT_PATH, SMALL_FONT_SIZE)
        self._font_m: FreeTypeFont = ImageFont.truetype(FONT_PATH, MEDIUM_FONT_SIZE)
        self._font_l: FreeTypeFont = ImageFont.truetype(FONT_PATH, LARGE_FONT_SIZE)

    def _save_image(self, image: Image) -> None:
        """saves image if specified in the config"""
        if self._display.spoke_config["developer"]["render_images"]:
            if not os.path.isdir("img"):
                os.mkdir("img")

            image_name = f"feecc_spoke/img/{self.name}-{str(dt.now()).split('.')[0]}.png"
            image.save(image_name)
            logging.info(f"Saved view {self.name} as '{image_name.split('/')[-1]}'")

    def _render_image(self, image: Image) -> None:
        """display the provided image and save it if needed"""
        self._save_image(image)
        logging.info(f"Rendering {self.name} view on the screen")
        self._epd.display(self._epd.getbuffer(image))

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def display(self) -> None:
        """a universal method that constructs the view and draws it onto a screen"""
        raise NotImplementedError


class Alert(View):
    """display a message with an icon (an alert)"""

    def __init__(
        self,
        context: Display,
        image_path: str,
        alert_message: str,
        font: tp.Optional[FreeTypeFont] = None,
    ) -> None:
        super().__init__(context)
        self._image_path: str = image_path
        self._message: str = alert_message
        self._font: FreeTypeFont = font if font else self._font_m

    @property
    def _no_of_lines(self) -> int:
        """get number of lines in the message"""
        return len(self._message.split("\n"))

    def display(self) -> None:
        # init image
        alert_screen = Image.new("1", (self._height, self._width), 255)
        alert_draw = ImageDraw.Draw(alert_screen)

        # draw the icon
        icon = Image.open(self._image_path)
        img_h, img_w = (50, 50)
        icon = icon.resize((img_h, img_w))
        alert_screen.paste(icon, (20, floor((self._width - img_h) / 2)))

        # draw the alert message
        message: str = self._message
        txt_h, txt_w = alert_draw.textsize(message, self._font)
        text_position = (
            20 + img_w + 10, floor((self._height - txt_h * self._no_of_lines) / 2) - 15
        )
        alert_draw.text(text_position, message, font=self._font, fill=0)

        # display the image
        self._render_image(alert_screen)
        sleep(3)


class FailedAuthorizationAlert(Alert):
    """display a message about failed authorization"""

    def __init__(self, context: Display) -> None:
        image_path: str = "feecc_spoke/img/cross.png"
        alert_message: str = "Авторизация\nне пройдена"
        super().__init__(context, image_path, alert_message)


class SuccessfulLogOutAlert(Alert):
    """display a message about failed authorization"""

    def __init__(self, context: Display) -> None:
        image_path: str = "feecc_spoke/img/tick.png"
        alert_message: str = "Сессия\nзавершена"
        super().__init__(context, image_path, alert_message)


class SuccessfulAuthorizationAlert(Alert):
    """display a message about successful authorization"""

    def __init__(self, context: Display) -> None:
        image_path: str = "feecc_spoke/img/tick.png"
        worker_position: str = context.associated_worker.position
        worker_short_name: str = context.associated_worker.short_name()
        alert_message: str = f"Авторизован\n{worker_position}\n{worker_short_name}"
        font: FreeTypeFont = ImageFont.truetype(FONT_PATH, SMALL_FONT_SIZE)
        super().__init__(context, image_path, alert_message, font)


class AuthorizeFirstAlert(Alert):
    """display a message about authorization needed to scan barcode"""

    def __init__(self, context: Display) -> None:
        image_path: str = "feecc_spoke/img/cross.png"
        alert_message: str = "Необходима\nавторизация"
        super().__init__(context, image_path, alert_message)


class BackendUnreachableAlert(Alert):
    """display a message about authorization needed to scan barcode"""

    def __init__(self, context: Display) -> None:
        image_path: str = "feecc_spoke/img/warning.png"
        alert_message: str = "Нет связи\nс сервером"
        super().__init__(context, image_path, alert_message)


class LoginScreen(View):
    """displays login screen"""

    def display(self) -> None:
        logging.info("Display login screen")

        # init image
        login_screen = Image.new("1", (self._height, self._width), 255)
        login_screen_draw = ImageDraw.Draw(login_screen)

        # draw the heading
        heading = "FEECC Spoke v1"
        w, h = login_screen_draw.textsize(heading, self._font_m)
        login_screen_draw.text((self._width - w / 2, 5), heading, font=self._font_m, fill=0)

        # draw the RFID sign
        rfid_image = Image.open("feecc_spoke/img/rfid.png")
        rfid_image = rfid_image.resize((50, 50))
        block_start = 10 + h + 5
        login_screen.paste(rfid_image, (35, block_start))

        # draw the message
        message = "Приложите\nпропуск\nк сканеру"
        login_screen_draw.text((35 + 50 + 10, block_start), message, font=self._font_s, fill=0)

        # draw the footer
        footer = f"spoke no.{self._display.spoke_config['general']['workbench_no']}"
        ipv4 = self._display.associated_spoke.ipv4()

        if ipv4:
            footer += f". IPv4: {ipv4}"

        w, h = login_screen_draw.textsize(footer, self._font_s)
        text_position = (self._width - w / 2, block_start + 50 + 3)
        login_screen_draw.text(text_position, footer, font=self._font_s, fill=0)

        # display the image
        self._render_image(login_screen)


class AwaitInputScreen(View):
    """displays the barcode scan prompt"""

    def display(self) -> None:
        logging.info("Display barcode scan prompt")

        image = Image.new("1", (self._height, self._width), 255)
        message = "Сканируйте\nштрихкод"

        footer = f"Авторизован {self._display.associated_worker.short_name()}"
        logging.debug(f"Footer: {footer}")

        image_draw = ImageDraw.Draw(image)
        barcode_image = Image.open("feecc_spoke/img/barcode.png")

        # draw the barcode icon
        logging.debug("Drawing the barcode icon")
        img_h, img_w = (50, 50)
        barcode_image = barcode_image.resize((img_h, img_w))
        image.paste(barcode_image, (10, 10))

        # draw the text
        logging.debug("Drawing the main message")
        image_draw.text((10 + img_w + 10, 10), message, font=self._font_m, fill=0)

        # draw the footer
        logging.debug("Drawing the footer")
        footer_h, footer_w = image_draw.textsize(footer, font=self._font_s)
        text_position = (floor((self._width - footer_w) / 2), 10 + img_h + 10)
        image_draw.text(text_position, footer, font=self._font_s, fill=0)

        # draw the image
        self._render_image(image)


class OngoingOperationScreen(View):
    """Displays the assembly timer"""

    def display(self) -> None:
        logging.info("Display assembly timer")
        time_image = Image.new("1", (self._height, self._width), 255)
        time_draw = ImageDraw.Draw(time_image)

        message = "ИДЕТ ЗАПИСЬ"
        w, h = time_draw.textsize(message, self._font_m)
        time_draw.text((self._width - w / 2, 10), message, font=self._font_m, fill=0)

        message = "Для завершения сканировать\nштрихкод еще раз"
        w, h = time_draw.textsize(message, self._font_s)
        text_position = (self._width - w / 2, 67)
        time_draw.text(text_position, message, font=self._font_s, fill=0, align="center")
        start_time = dt.now()

        while self.name == self._display.state:
            timer_delta = dt.now() - start_time
            timer = dt.utcfromtimestamp(timer_delta.total_seconds())
            message = timer.strftime("%H:%M:%S")

            w, h = time_draw.textsize(message, self._font_l)
            nw_w = floor(self._width - w / 2)
            time_draw.rectangle((nw_w, 30, nw_w + w, 30 + h), fill=255)
            time_draw.text((nw_w, 30), message, font=self._font_l, fill=0)
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
