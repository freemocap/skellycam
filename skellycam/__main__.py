# __main__.py
import logging
import multiprocessing
import sys
from multiprocessing import Process
from pathlib import Path

from skellycam.api.server.run_skellycam_server import run_server
from skellycam.utilities.clean_path import clean_path
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)

PATH_TO_SKELLYCAM_MAIN = str(Path(__file__).absolute())


def main(qt: bool = False):
    logger.info(f"Running from __main__: {__name__} - {clean_path(__file__)}")
    if sys.platform == "win32":
        setup_app_id_for_windows()
    if qt:
        from skellycam.gui.gui_main import gui_main
        # multiprocessing.set_start_method("fork") # might be needed for MacOS or Linux?

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
    else:
        run_server()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main(qt=False)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt - shutting down!")
    except Exception:
        raise Exception
    print("\n\n--------------------------------------------------\n--------------------------------------------------")
    print("Thank you for using SkellyCam \U0001F480 \U0001F4F8 \U00002728 \U0001F495")
    print("--------------------------------------------------\n--------------------------------------------------\n\n")
