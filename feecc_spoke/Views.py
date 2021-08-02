import logging
from datetime import datetime as dt

from PIL import Image, ImageDraw

from .ViewBase import Icon, View


class LoginScreen(View):
    """displays login screen"""

    def display(self) -> None:
        logging.info("Display login screen")

        # init image
        login_screen = self._get_image()
        login_screen_draw = ImageDraw.Draw(login_screen)

        # draw the heading
        heading = "FEECC Spoke v1"
        w, _ = self._align_center(heading, self._font_m)
        _, h = login_screen_draw.textsize(heading, self._font_m)
        login_screen_draw.text((w, 5), heading, font=self._font_m, fill=0)

        # draw the RFID sign
        rfid_image = Image.open(Icon.rfid)
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

        w, _ = self._align_center(footer, self._font_s)
        text_position = (w, block_start + 50 + 3)
        login_screen_draw.text(text_position, footer, font=self._font_s, fill=0)

        # display the image
        self._render_image(login_screen)


class AwaitInputScreen(View):
    """displays the barcode scan prompt"""

    def display(self) -> None:
        logging.info("Display barcode scan prompt")

        image = self._get_image()
        message = "Сканируйте\nштрихкод"

        footer = f"Авторизован {self._display.associated_worker.short_name()}"
        footer = self._ensure_fitting(footer, self._font_s, 10)
        logging.debug(f"Footer: {footer}")

        image_draw = ImageDraw.Draw(image)
        barcode_image = Image.open(Icon.barcode_scanner)

        # draw the barcode icon
        img_h, img_w = (50, 50)
        barcode_image = barcode_image.resize((img_h, img_w))
        image.paste(barcode_image, (10, 10))

        # draw the text
        image_draw.text((10 + img_w + 10, 10), message, font=self._font_m, fill=0)

        # draw the footer
        footer_w, _ = self._align_center(footer, font=self._font_s)
        text_position = footer_w, 10 + img_h + 10
        image_draw.text(text_position, footer, font=self._font_s, fill=0, align="center")

        # draw the image
        self._render_image(image)


class OngoingOperationScreen(View):
    """Displays the assembly timer"""

    def display(self) -> None:
        logging.info("Display assembly timer")
        time_image = self._get_image()
        time_draw = ImageDraw.Draw(time_image)

        message = "ИДЕТ ЗАПИСЬ"
        w, _ = self._align_center(message, self._font_m)
        time_draw.text((w, 10), message, font=self._font_m, fill=0)

        message = "Для завершения сканировать\nштрихкод еще раз"
        w, _ = self._align_center(message, self._font_s)
        text_position = w, 67
        time_draw.text(text_position, message, font=self._font_s, fill=0, align="center")
        start_time = dt.now()

        while self.name == self._display.state:
            timer_delta = dt.now() - start_time
            timer = dt.utcfromtimestamp(timer_delta.total_seconds())
            message = timer.strftime("%H:%M:%S")

            w, h = time_draw.textsize(message, self._font_l)
            nw_w, _ = self._align_center(message, self._font_l)
            time_draw.rectangle((nw_w, 30, nw_w + w, 30 + h), fill=255)
            time_draw.text((nw_w, 30), message, font=self._font_l, fill=0)
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
        logging.info("Clearing the screen")
        self._epd.init()
        self._epd.Clear(0x00)  # fill with black to remove stuck pixels
        self._epd.Clear(0xFF)  # fill with white
        logging.debug("Finished clearing the screen")
