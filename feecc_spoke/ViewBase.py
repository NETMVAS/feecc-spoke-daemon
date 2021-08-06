from __future__ import annotations
from dataclasses import dataclass
import logging
import os
import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime as dt
from time import sleep, time

from PIL import Image, ImageDraw, ImageFont

if tp.TYPE_CHECKING:
    from .waveshare_epd import epd2in13d
    from PIL.ImageFont import FreeTypeFont
    from Display import Display

# paths
FONT_PATH: str = "feecc_spoke/fonts/helvetica-cyrillic-bold.ttf"
IMAGE_DIRECTORY_PATH: str = "feecc_spoke/img"

# colors (single channel)
MAIN_COLOR: int = 0
BG_COLOR: int = 255

# font sizes
SMALL_FONT_SIZE: int = 11
MEDIUM_FONT_SIZE: int = 20
LARGE_FONT_SIZE: int = 36

# misc
ALERT_DISPLAY_TIME: int = 1


class View(ABC):
    """
    abstract base class for all the views (states) to inherit from.
    each view is responsible for an image drawn on the screen
    """

    def __init__(self, context: Display) -> None:
        # associated display parameters
        self._display: Display = context
        self._epd: epd2in13d.EPD = self._display.epd

        # by default the display is rotated sideways
        self._height: int = self._epd.width
        self._width: int = self._epd.height

        # fonts
        logging.debug(f"Using font {os.path.basename(FONT_PATH)}")
        self._font_s: FreeTypeFont = ImageFont.truetype(FONT_PATH, SMALL_FONT_SIZE)
        self._font_m: FreeTypeFont = ImageFont.truetype(FONT_PATH, MEDIUM_FONT_SIZE)
        self._font_l: FreeTypeFont = ImageFont.truetype(FONT_PATH, LARGE_FONT_SIZE)

    def _get_image(self, fill: int = BG_COLOR) -> Image:
        return Image.new("1", (self._width, self._height), fill)

    def _save_image(self, image: Image) -> None:
        """saves image if specified in the config"""
        if not os.path.isdir("img"):
            os.mkdir("img")

        image_name = f"{IMAGE_DIRECTORY_PATH}/{self.name}-{str(dt.now()).split('.')[0]}.png"
        image.save(image_name)
        logging.info(f"Saved view {self.name} as '{image_name.split('/')[-1]}'")

    def _render_image(self, image: Image) -> None:
        """display the provided image and save it if needed"""
        start_time: float = time()

        if self._display.spoke_config["developer"]["render_images"]:
            self._save_image(image)

        if self._rotate:
            image = image.rotate(180)

        logging.info(f"Rendering {self.name} view on the screen")
        self._epd.display(self._epd.getbuffer(image))

        end_time: float = time()
        logging.debug(f"Image rendering took {round(end_time-start_time, 3)} s.")

    def _align_center(self, text: str, font: FreeTypeFont) -> tp.Tuple[int, int]:
        """get the coordinates of the upper left corner for the centered text"""
        sample_image = self._get_image()
        sample_draw = ImageDraw.Draw(sample_image)
        txt_w, txt_h = sample_draw.textsize(text, font)

        # https://stackoverflow.com/questions/59008322/pillow-imagedraw-text-coordinates-to-center/59008967#59008967
        offset_w, offset_h = font.getoffset(text)
        txt_h += offset_h
        txt_w += offset_w

        text_position = int((self._width - txt_w) / 2), int((self._height - txt_h) / 2)
        return text_position

    def _ensure_fitting(self, text: str, font: FreeTypeFont, min_offset: int = 5) -> str:
        """make sure provided text fits on the screen and add line breaks if it doesn't"""
        modified_text: str = text
        sample_image = self._get_image()
        sample_draw = ImageDraw.Draw(sample_image)

        def _is_fitting(message: str) -> bool:
            txt_w, _ = sample_draw.textsize(message, font)
            offset_w, _ = font.getoffset(message)
            txt_w += offset_w
            msg_w: int = txt_w + (min_offset * 2)
            return msg_w <= self._width

        def _insert_break(msg: str, break_pos_: int) -> str:
            msg_: tp.List[str] = msg.split()
            msg_.insert(break_pos_, "\n")
            new_msg: str = " ".join(msg_)
            new_msg.replace(" \n ", "\n")
            return new_msg

        break_pos: int = 0
        while not _is_fitting(modified_text) and break_pos < len(text.split()):
            modified_text = _insert_break(text, break_pos)
            break_pos += 1

        return modified_text

    @property
    def _rotate(self) -> bool:
        return bool(self._display.spoke_config["screen"]["rotate_output"])

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

    def display(self) -> None:
        # init image
        alert_screen = self._get_image()
        alert_draw = ImageDraw.Draw(alert_screen)

        # draw the icon
        icon = Image.open(self._image_path)
        img_w, img_h = (50, 50)
        icon = icon.resize((img_w, img_h))
        alert_screen.paste(icon, (20, int((self._height - img_h) / 2)))

        # draw the alert message
        message: str = self._message
        _, txt_h = self._align_center(message, self._font)
        text_position = 20 + img_w + 10, txt_h
        alert_draw.text(text_position, message, font=self._font, fill=MAIN_COLOR, align="center")

        # display the image
        self._render_image(alert_screen)
        sleep(ALERT_DISPLAY_TIME)


@dataclass(frozen=True)
class Icon:
    """stores paths to all the icon image files"""

    _icon_dir: str = IMAGE_DIRECTORY_PATH
    tick: str = f"{_icon_dir}/tick.png"
    cross: str = f"{_icon_dir}/cross.png"
    warning: str = f"{_icon_dir}/warning.png"
    rfid: str = f"{_icon_dir}/rfid.png"
    barcode_scanner: str = f"{_icon_dir}/barcode.png"
