import logging
import typing as tp
from datetime import datetime as dt
from math import floor
from time import sleep

from PIL import Image, ImageDraw, ImageFont

from Spoke import Spoke
from Worker import Worker
from waveshare_epd import epd2in13d

# Set output log level
logging.basicConfig(level=logging.DEBUG)


class Display:
    def __init__(
            self,
            associated_worker: Worker,
            associated_spoke: Spoke
    ) -> None:
        self.associated_worker: Worker = associated_worker
        self.associated_spoke: Spoke = associated_spoke
        self.spoke_config: tp.Dict[str, tp.Dict[str, tp.Any]] = self.associated_spoke.config
        self.state = 0  # state no as described in architecture docs
        self.latest_known_state = -1
        self.epd = epd2in13d.EPD()
        self.font_s = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 11)
        self.font_m = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 20)
        self.font_l = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 36)

    def _screen_cleanup(self) -> None:
        """clear the screen before and after usage"""
        logging.info("Clearing the screen")
        self.epd.init()
        self.epd.Clear(0x00)  # fill with black to remove stuck pixels
        self.epd.Clear(0xFF)  # fill with white
        logging.debug("Finished clearing the screen")

    def end_session(self) -> None:
        """clear the screen if execution is interrupted or script exits"""

        self._screen_cleanup()
        epd2in13d.epdconfig.module_exit()

    def _save_image(self, image: Image) -> None:
        """saves image if specified in the config"""

        if self.spoke_config["developer"]["render_images"]:
            image.save(f"img/state-{self.state}-{str(dt.now()).split('.')[0]}.png")

    def _render_login_screen(self) -> None:
        """displays login screen"""

        logging.info("Display login screen")

        # init image
        login_screen = Image.new("1", (self.epd.height, self.epd.width), 255)
        login_screen_draw = ImageDraw.Draw(login_screen)

        # draw the heading
        heading = "FEECC Spoke v1"
        w, h = login_screen_draw.textsize(heading, self.font_m)
        login_screen_draw.text((self.epd.width - w / 2, 5), heading, font=self.font_m, fill=0)

        # draw the RFID sign
        rfid_image = Image.open("img/rfid.png")
        rfid_image = rfid_image.resize((50, 50))
        block_start = 10 + h + 5
        login_screen.paste(rfid_image, (35, block_start))

        # draw the message
        message = "Приложите\nпропуск\nк сканеру"
        login_screen_draw.text((35 + 50 + 10, block_start), message, font=self.font_s, fill=0)

        # draw the footer
        footer = f"spoke no.{self.spoke_config['general']['spoke_num']}"
        ipv4 = self.associated_spoke.ipv4()

        if ipv4:
            footer += f". IPv4: {ipv4}"

        w, h = login_screen_draw.textsize(footer, self.font_s)
        login_screen_draw.text((self.epd.width - w / 2, block_start + 50 + 3), footer, font=self.font_s, fill=0)

        # display the image
        self._save_image(login_screen)
        self.epd.display(self.epd.getbuffer(login_screen))

    def _authorization(self) -> None:
        """displays authorization screen"""

        logging.info("Display authorization screen")

        # init image
        auth_screen = Image.new("1", (self.epd.height, self.epd.width), 255)
        auth_screen_draw = ImageDraw.Draw(auth_screen)

        if not self.associated_worker.is_authorized:
            # display a message about failed authorization

            # draw the cross sign
            cross_image = Image.open("img/cross.png")
            img_h, img_w = (50, 50)
            cross_image = cross_image.resize((img_h, img_w))
            auth_screen.paste(cross_image, (20, floor((self.epd.width - img_h) / 2)))

            # draw the message
            message = "Авторизация\nне пройдена"
            txt_h, txt_w = auth_screen_draw.textsize(message, self.font_m)
            auth_screen_draw.text(
                (20 + img_w + 10, floor((self.epd.height - txt_h) / 2) - 15),
                message,
                font=self.font_m,
                fill=0
            )

            # display the image
            self._save_image(auth_screen)
            self.epd.display(self.epd.getbuffer(auth_screen))
            sleep(5)

            # since authorization failed switch back to login screen
            self.state = 0
            return

        else:
            # authorization success
            # display a message about successful authorization

            # draw the tick sign
            tick_image = Image.open("img/tick.png")
            img_h, img_w = (50, 50)
            tick_image = tick_image.resize((img_h, img_w))
            auth_screen.paste(tick_image, (20, floor((self.epd.width - img_h) / 2)))

            try:
                message = f"Авторизован\n{self.associated_worker.position}\n{self.associated_worker.short_name()}"

                # draw the message
                auth_screen_draw.text((20 + img_w + 10, 30), message, font=self.font_s, fill=0)

            except KeyError:
                message = "Успешная\nавторизация"

                # draw the message
                auth_screen_draw.text((20 + img_w + 10, 30), message, font=self.font_m, fill=0)

            # display the image
            self._save_image(auth_screen)
            self.epd.display(self.epd.getbuffer(auth_screen))
            sleep(5)

            # switch to barcode await screen
            self.state = 2
            return

    def _await_input(self) -> None:
        # display barcode scan prompt
        logging.info(f"Display barcode scan prompt")

        image = Image.new("1", (self.epd.height, self.epd.width), 255)
        message = "Сканируйте\nштрихкод"

        footer = f"Авторизован {self.associated_worker.short_name()}"
        logging.debug(f"Footer: {footer}")

        image_draw = ImageDraw.Draw(image)
        barcode_image = Image.open("img/barcode.png")

        # draw the barcode icon
        logging.debug(f"Drawing the barcode icon")
        img_h, img_w = (50, 50)
        barcode_image = barcode_image.resize((img_h, img_w))
        image_draw.paste(barcode_image, (10, 10))

        # draw the text
        logging.debug(f"Drawing the main message")
        image_draw.text((10 + img_w + 5, 10), message, font=self.font_l, fill=0)

        # draw the footer
        logging.debug(f"Drawing the footer")
        footer_h, footer_w = image_draw.textsize(footer, font=self.font_m)
        image_draw.text((floor(self.epd.width - footer_w / 2), 10 + img_h + 10), footer, font=self.font_m, fill=0)

        # draw the image
        logging.info(f"Drawing the await screen image")
        self._save_image(image_draw)
        self.epd.display(self.epd.getbuffer(image_draw))

    def _ongoing_operation(self) -> None:
        # Display assembly timer
        logging.info("Display assembly timer")
        time_image = Image.new("1", (self.epd.height, self.epd.width), 255)
        time_draw = ImageDraw.Draw(time_image)

        message = "ИДЕТ ЗАПИСЬ"
        w, h = time_draw.textsize(message, self.font_m)
        time_draw.text((self.epd.width - w / 2, 10), message, font=self.font_m, fill=0)

        message = "Для завершения сканировать\nштрихкод еще раз"
        w, h = time_draw.textsize(message, self.font_s)
        time_draw.text((self.epd.width - w / 2, 67), message, font=self.font_s, fill=0, align="center")
        start_time = dt.now()

        while self.state == 3:
            timer_delta = dt.now() - start_time
            timer = dt.utcfromtimestamp(timer_delta.total_seconds())
            message = timer.strftime("%H:%M:%S")

            w, h = time_draw.textsize(message, self.font_l)
            nw_w = floor(self.epd.width - w / 2)
            time_draw.rectangle((nw_w, 30, nw_w + w, 30 + h), fill=255)
            time_draw.text(
                (nw_w, 30), message, font=self.font_l, fill=0
            )
            new_image = time_image.crop([nw_w, 30, nw_w + w, 30 + h])
            time_image.paste(new_image, (nw_w, 30))
            self.epd.DisplayPartial(self.epd.getbuffer(time_image))

        self._save_image(time_image)

    def run(self) -> None:
        """enter an infinite loop to monitor own state changing the output accordingly"""

        while True:
            if self.latest_known_state != self.state:
                logging.info(f"Display state changed from {self.latest_known_state} to {self.state}")
                self.latest_known_state = self.state
                self._screen_cleanup()

                if self.state == 0:  # login screen
                    self._render_login_screen()
                elif self.state == 1:  # authorization status and awaiting barcode event
                    self._authorization()
                elif self.state == 2:  # authorized, await input
                    self._await_input()
                elif self.state == 3:  # ongoing operation
                    self._ongoing_operation()
                else:
                    logging.error(f"Wrong state: {self.state}. Exiting.")
                    exit()
