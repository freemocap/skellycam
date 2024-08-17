# __main__.py
import logging
import multiprocessing
from multiprocessing import Process

from skellycam.api.server.run_server import run_uvicorn_server
from skellycam.gui.qt.qt_main import qt_gui_main
from skellycam.utilities.clean_path import clean_path

logger = logging.getLogger(__name__)


def main():
    multiprocessing.freeze_support()
    # multiprocessing.set_start_method("fork") # might be needed for MacOS or Linux?
    logger.info(f"Running from __main__: {__name__} - {clean_path(__file__)}")

    frontend_process = multiprocessing.Process(target=qt_gui_main)
    logger.info(f"Starting frontend process")
    frontend_process.start()

    backend_process = Process(target=run_uvicorn_server)
    logger.info(f"Starting backend process")
    backend_process.start()

    frontend_process.join()
    backend_process.join()
    logger.info(f"Exiting `main`...")


if __name__ == "__main__":
    main()
    print("\n\n--------------------------------------------------\n--------------------------------------------------")
    print("Thank you for using SkellyCam \U0001F480 \U0001F4F8 \U00002728 \U0001F495")
    print("--------------------------------------------------\n--------------------------------------------------\n\n")
