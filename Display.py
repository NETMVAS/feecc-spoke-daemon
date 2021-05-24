import logging
from datetime import datetime as dt
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13d
from math import floor
from time import sleep
from funcs import get_own_ip, short_name

# Set output log level
logging.basicConfig(level=logging.DEBUG)


class Display:
    def __init__(self, config) -> None:
        self.spoke_config = config
        self.state = 0  # state no as described in architecture docs
        self.latest_known_state = -1
        self.epd = epd2in13d.EPD()
        self.ipv4 = get_own_ip()
        self.font_s = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 11)
        self.font_m = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 20)
        self.font_l = ImageFont.truetype("helvetica-cyrillic-bold.ttf", 36)

    def screen_cleanup(self) -> None:
        """clear the screen before and after usage"""
        logging.info("Clearing the screen")
        self.epd.init()
        self.epd.Clear(0x00)  # fill with black to remove stuck pixels
        self.epd.Clear(0xFF)  # fill with white
        logging.debug("Finished clearing the screen")

    def end_session(self) -> None:
        """clear the screen if execution is interrupted or script exits"""

        self.screen_cleanup()
        epd2in13d.epdconfig.module_exit()

    def render_login_screen(self) -> None:
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
        footer = f"spoke no.{self.spoke_config['general']['spoke_num']}. IPv4: {self.ipv4}"
        w, h = login_screen_draw.textsize(footer, self.font_s)
        login_screen_draw.text((self.epd.width - w / 2, block_start + 50 + 3), footer, font=self.font_s, fill=0)

        # display the image
        self.epd.display(self.epd.getbuffer(login_screen))

    def authorization(self, is_authorized: bool = False, **kwargs):
        """displays authorization screen"""

        logging.info("Display authorization screen")

        # init image
        auth_screen = Image.new("1", (self.epd.height, self.epd.width), 255)
        auth_screen_draw = ImageDraw.Draw(auth_screen)
        
        if not is_authorized:
            # display a message about failed authorization

            # draw the cross sign
            cross_image = Image.open("img/cross.png")
            img_h, img_w = (50, 50)
            cross_image = cross_image.resize((img_h, img_w))
            auth_screen.paste(cross_image, (20, floor((self.epd.width - img_h) / 2)))

            # draw the message
            message = "Авторизация\nне пройдена"
            txt_h, txt_w = auth_screen_draw.textsize(message, self.font_m)
            auth_screen_draw.text((20 + img_w + 10, floor((self.epd.height - txt_h) / 2) - 15), message, font=self.font_m, fill=0)

            # display the image
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
                message = f"Авторизован\n{kwargs['worker_position']}\n{short_name(kwargs['worker_name'])}"

                # draw the message
                txt_h, txt_w = auth_screen_draw.textsize(message, self.font_s)
                auth_screen_draw.text((20 + img_w + 10, 30), message, font=self.font_s, fill=0)

            except KeyError:
                message = "Успешная\nавторизация"

                # draw the message
                txt_h, txt_w = auth_screen_draw.textsize(message, self.font_m)
                auth_screen_draw.text((20 + img_w + 10, 30), message, font=self.font_m, fill=0)

            # display the image
            self.epd.display(self.epd.getbuffer(auth_screen))
            sleep(5)

            # todo
            # switch to barcode await screen
            pass
            return

    def ongoing_operation(self) -> None:
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

        while self.state == 2:
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

    def run(self):
        """enter an infinite loop to monitor own state changing the output accordingly"""

        while True:
            if self.latest_known_state != self.state:
                logging.info(f"Display state changed from {self.latest_known_state} to {self.state}")
                self.latest_known_state = self.state
                self.screen_cleanup()

                if self.state == 0:  # login screen
                    self.render_login_screen()
                    continue

                elif self.state == 1:  # authorization status and awaiting barcode event
                    self.authorization(
                        is_authorized=True,
                        # worker_name="Петров Петр Петрович",
                        worker_position="Младший Инженер"
                    )
                    continue

                elif self.state == 2:  # ongoing operation
                    self.ongoing_operation()
                    continue

                elif self.state == 3:
                    pass

                else:
                    logging.error(f"Wrong state: {self.state}. Exiting.")
                    exit()
