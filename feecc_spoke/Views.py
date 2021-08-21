from datetime import datetime as dt

from loguru import logger
from PIL import Image, ImageDraw

from .ViewBase import BG_COLOR, MAIN_COLOR, Icon, View


class LoginScreen(View):
    """displays login screen"""

    def display(self) -> None:
        logger.info("Display login screen")

        # init image
        login_screen = self._get_image()
        login_screen_draw = ImageDraw.Draw(login_screen)

        # draw the heading
        heading = "FEECC Spoke v1"
        w, _ = self._align_center(heading, self._font_m)
        _, h = login_screen_draw.textsize(heading, self._font_m)
        login_screen_draw.text((w, 5), heading, font=self._font_m, fill=MAIN_COLOR)

        # draw the RFID sign
        rfid_image = Image.open(Icon.rfid)
        rfid_image = rfid_image.resize((50, 50))
        block_start = 10 + h + 5
        login_screen.paste(rfid_image, (35, block_start))

        # draw the message
        message = "Приложите\nпропуск\nк сканеру"
        login_screen_draw.text((35 + 50 + 10, block_start), message, font=self._font_s, fill=MAIN_COLOR)

        # draw the footer
        footer = f"spoke no.{self._display.spoke_config['general']['workbench_no']}"
        ipv4 = self._display.associated_spoke.ipv4

        if ipv4 is not None:
            footer += f". IPv4: {ipv4}"

        w, _ = self._align_center(footer, self._font_s)
        text_position = (w, block_start + 50 + 3)
        login_screen_draw.text(text_position, footer, font=self._font_s, fill=MAIN_COLOR)

        # display the image
        self._render_image(login_screen)


class OngoingOperationScreen(View):
    """Displays the assembly timer"""

    def display(self) -> None:
        logger.info("Display assembly timer")
        time_image = self._get_image()
        time_draw = ImageDraw.Draw(time_image)

        message = "ИДЕТ ЗАПИСЬ"
        w, _ = self._align_center(message, self._font_m)
        time_draw.text((w, 10), message, font=self._font_m, fill=MAIN_COLOR)

        message = "Для завершения сканировать\nштрихкод еще раз"
        w, _ = self._align_center(message, self._font_s)
        text_position = w, 67
        time_draw.text(text_position, message, font=self._font_s, fill=MAIN_COLOR, align="center")
        start_time = dt.now()

        while self._display.associated_spoke.operation_ongoing:
            timer_delta = dt.now() - start_time
            timer = dt.utcfromtimestamp(timer_delta.total_seconds())
            message = timer.strftime("%H:%M:%S")

            w, h = time_draw.textsize(message, self._font_l)
            nw_w, _ = self._align_center(message, self._font_l)
            time_draw.rectangle((nw_w, 30, nw_w + w, 30 + h), fill=BG_COLOR)
            time_draw.text((nw_w, 30), message, font=self._font_l, fill=MAIN_COLOR)
            new_image = time_image.crop([nw_w, 30, nw_w + w, 30 + h])
            time_image.paste(new_image, (nw_w, 30))

            if self._rotate:
                time_image_rotated = time_image.rotate(180)
                self._epd.DisplayPartial(self._epd.getbuffer(time_image_rotated))
            else:
                self._epd.DisplayPartial(self._epd.getbuffer(time_image))


class BlankScreen(View):
    """used to clear the screen before and after usage"""

    def display(self) -> None:
        logger.info("Clearing the screen")
        self._epd.init()
        self._epd.Clear(0x00)  # fill with black to remove stuck pixels
        self._epd.Clear(0xFF)  # fill with white
        logger.debug("Finished clearing the screen")
