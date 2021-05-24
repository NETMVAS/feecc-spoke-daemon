from Display import Display
import atexit
from time import sleep
import threading
import logging
import funcs

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    filename="spoke-daemon.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)

config = funcs.read_configuration("config.yaml")  # parse configuration
display = Display(config)  # instantiate Display
display_thread = threading.Thread(target=display.run)  # make a thread for the display to run in


@atexit.register  # define the behaviour when the script execution is completed
def end_session() -> None:
    """clear the display, release SPI and join the thread before exiting"""

    display.end_session()
    display_thread.join(timeout=1)


# entry point
if __name__ == "__main__":
    display_thread.start()  # start the display daemon
    sleep(20)
