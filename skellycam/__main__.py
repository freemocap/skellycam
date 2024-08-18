# __main__.py
import logging
import multiprocessing
from multiprocessing import Process

from skellycam.api.server.server_main import run_server
from skellycam.gui.gui_main import gui_main
from skellycam.system.logging_configuration.configure_logging import configure_logging
from skellycam.system.logging_configuration.log_level_enum import LogLevels
from skellycam.utilities.clean_path import clean_path

configure_logging(level=LogLevels.DEBUG)

logger = logging.getLogger(__name__)


def main():
    multiprocessing.freeze_support()
    # multiprocessing.set_start_method("fork") # might be needed for MacOS or Linux?
    logger.info(f"Running from __main__: {__name__} - {clean_path(__file__)}")

    shutdown_event = multiprocessing.Event()

    frontend_process = multiprocessing.Process(target=gui_main, args=(shutdown_event,))
    logger.info(f"Starting frontend process")
    frontend_process.start()

    backend_process = Process(target=run_server, args=(shutdown_event,))
    logger.info(f"Starting backend process")
    backend_process.start()

    frontend_process.join()
    logger.info("Frontend process ended - terminating backend process")
    shutdown_event.set()
    backend_process.join()
    logger.info(f"Exiting `main`...")


if __name__ == "__main__":
    main()
    print("\n\n--------------------------------------------------\n--------------------------------------------------")
    print("Thank you for using SkellyCam \U0001F480 \U0001F4F8 \U00002728 \U0001F495")
    print("--------------------------------------------------\n--------------------------------------------------\n\n")
