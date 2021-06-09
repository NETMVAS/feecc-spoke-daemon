import logging
import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime as dt
from math import floor

from PIL import Image, ImageDraw, ImageFont

import waveshare_epd.epd2in13d


# a View is an image unit - one drawable medium,
# which can be displayed on the screen by executing
# the display method of the View subclass object


class View(ABC):
    """
    abstract base class for all the views (states) to inherit from.
    each view is responsible for an image drawn on the screen
    """

    def __init__(self) -> None:
        # associated display parameters
        self._display = None
        self._epd: tp.Optional[waveshare_epd.epd2in13d.EPD] = None
        self._height: int = 0
        self._width: int = 0

        # fonts
        self._font_s = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 11)
        self._font_m = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 20)
        self._font_l = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 36)

    @property
    def context(self):
        return self._display

    @context.setter
    def context(self, context) -> None:
        self._display = context
        self._epd = self._display.epd
        self._height = self._epd.height
        self._width = self._epd.width

        logging.debug(f"{self.name} context set as {self.context}")

    def _save_image(self, image: Image) -> None:
        """saves image if specified in the config"""

        if self._display.spoke_config["developer"]["render_images"]:
            image_name = f"img/state-{self.name}-{str(dt.now()).split('.')[0]}.png"
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

        pass


class LoginScreen(View):
    """displays login screen"""

    def __init__(self) -> None:
        super().__init__()

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
        login_screen_draw.text((self._width - w / 2, block_start + 50 + 3), footer, font=self._font_s, fill=0)

        # display the image
        self._render_image(login_screen)


class FailedAuthorizationScreen(View):
    """display a message about failed authorization"""

    def __init__(self) -> None:
        super().__init__()

    def display(self) -> None:
        # init image
        auth_screen = Image.new("1", (self._height, self._width), 255)
        auth_screen_draw = ImageDraw.Draw(auth_screen)

        # draw the cross sign
        cross_image = Image.open("img/cross.png")
        img_h, img_w = (50, 50)
        cross_image = cross_image.resize((img_h, img_w))
        auth_screen.paste(cross_image, (20, floor((self._width - img_h) / 2)))

        # draw the message
        message = "Авторизация\nне пройдена"
        txt_h, txt_w = auth_screen_draw.textsize(message, self._font_m)
        auth_screen_draw.text(
            (20 + img_w + 10, floor((self._height - txt_h) / 2) - 15),
            message,
            font=self._font_m,
            fill=0
        )

        # display the image
        self._render_image(auth_screen)


class SuccessfulAuthorizationScreen(View):
    """display a message about successful authorization"""

    def __init__(self) -> None:
        super().__init__()

    def display(self) -> None:
        # init image
        auth_screen = Image.new("1", (self._height, self._width), 255)
        auth_screen_draw = ImageDraw.Draw(auth_screen)

        # draw the tick sign
        tick_image = Image.open("img/tick.png")
        img_h, img_w = (50, 50)
        tick_image = tick_image.resize((img_h, img_w))
        auth_screen.paste(tick_image, (20, floor((self._width - img_h) / 2)))

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
        self._render_image(auth_screen)


class AwaitInputScreen(View):
    """displays the barcode scan prompt"""

    def __init__(self) -> None:
        super().__init__()

    def display(self) -> None:
        logging.info(f"Display barcode scan prompt")

        image = Image.new("1", (self._height, self._width), 255)
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
        image_draw.text((floor((self._width - footer_w) / 2), 10 + img_h + 10), footer, font=self._font_s, fill=0)

        # draw the image
        self._render_image(image)


class OngoingOperationScreen(View):
    """Displays the assembly timer"""

    def __init__(self) -> None:
        super().__init__()

    def display(self) -> None:
        logging.info("Display assembly timer")
        time_image = Image.new("1", (self._height, self._width), 255)
        time_draw = ImageDraw.Draw(time_image)

        message = "ИДЕТ ЗАПИСЬ"
        w, h = time_draw.textsize(message, self._font_m)
        time_draw.text((self._width - w / 2, 10), message, font=self._font_m, fill=0)

        message = "Для завершения сканировать\nштрихкод еще раз"
        w, h = time_draw.textsize(message, self._font_s)
        time_draw.text((self._width - w / 2, 67), message, font=self._font_s, fill=0, align="center")
        start_time = dt.now()

        while self.name == self.context.state:
            timer_delta = dt.now() - start_time
            timer = dt.utcfromtimestamp(timer_delta.total_seconds())
            message = timer.strftime("%H:%M:%S")

            w, h = time_draw.textsize(message, self._font_l)
            nw_w = floor(self._width - w / 2)
            time_draw.rectangle((nw_w, 30, nw_w + w, 30 + h), fill=255)
            time_draw.text(
                (nw_w, 30), message, font=self._font_l, fill=0
            )
            new_image = time_image.crop([nw_w, 30, nw_w + w, 30 + h])
            time_image.paste(new_image, (nw_w, 30))
            self._epd.DisplayPartial(self._epd.getbuffer(time_image))


class BlankScreen(View):
    """used to clear the screen before and after usage"""

    def __init__(self) -> None:
        super().__init__()

    def display(self) -> None:
        logging.info("Clearing the screen")
        self._epd.init()
        self._epd.Clear(0x00)  # fill with black to remove stuck pixels
        self._epd.Clear(0xFF)  # fill with white
        logging.debug("Finished clearing the screen")
