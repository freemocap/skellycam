import argparse
import logging
import multiprocessing
import sys
import time
from pathlib import Path

from skellycam.skellycam_server import run_server
from skellycam.utilities.clean_path import clean_path
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)

PATH_TO_SKELLYCAM_MAIN = str(Path(__file__).absolute())


def main(qt: bool = True) -> None:
    """
    Main function to start the SkellyCam application.

    Parameters
    ----------
    qt : bool, optional
        Whether to start the application with a Qt GUI (default is False)
    """
    logger.info(f"Running from __main__: {__name__} - {clean_path(__file__)}")
    if sys.platform == "win32":
        setup_app_id_for_windows()

    global_kill_flag = multiprocessing.Value('b', False)
    if qt:
        from skellycam.qt_gui.gui_main import gui_main

        backend_process = multiprocessing.Process(target=run_server, args=(global_kill_flag,))
        logger.info("Starting backend process")
        backend_process.start()
        time.sleep(1)  # Give the backend time to startup
        frontend_process = multiprocessing.Process(target=gui_main, args=(global_kill_flag,))
        logger.info("Starting frontend process")
        frontend_process.start()

        while frontend_process.is_alive() and backend_process.is_alive():
            frontend_process.join(timeout=1)
            backend_process.join(timeout=1)
        logger.info(
            f"Frontend process status: {frontend_process.is_alive()}, Backend process status: {backend_process.is_alive()} - Shutting down...")
        global_kill_flag.value = True
        backend_process.join()
        frontend_process.join()
        logger.info("Exiting `main`...")
    else:
        run_server(global_kill_flag=global_kill_flag)


if __name__ == "__main__":
    """
    Entry point for the SkellyCam application.

    This script can be run with or without a Qt GUI. By default, the application runs without the GUI.
    To start the application with a Qt GUI, use the --qt flag.

    Usage
    -----
    Without GUI:
        python __main__.py

    With GUI:
        python __main__.py --qt
    """
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="Start the SkellyCam application.")
    parser.add_argument('--qt', action='store_true', default=True, help="Start the application with a Qt GUI.")
    args = parser.parse_args()

    try:
        main(qt=args.qt)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt - shutting down!")
    except Exception as e:
        logger.exception("An unexpected error occurred", exc_info=e)
        raise
    print("\n\n--------------------------------------------------\n--------------------------------------------------")
    print("Thank you for using SkellyCam \U0001F480 \U0001F4F8 \U00002728 \U0001F495")
    print("--------------------------------------------------\n--------------------------------------------------\n\n")
