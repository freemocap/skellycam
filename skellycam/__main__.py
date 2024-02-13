# __main__.py
import multiprocessing
import time
from multiprocessing import freeze_support

from skellycam.backend.run_backend import run_backend
from skellycam.system.logging_configuration.configure_logging import (
    configure_logging,
)

from skellycam.system.logging_configuration.log_level_enum import LogLevel

from skellycam.frontend.run_frontend import run_frontend

from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

configure_logging(LogLevel.TRACE)
import logging

logger = logging.getLogger(__name__)

BACKEND_TIMEOUT = 30

def main_loop():
    logger.info("Starting `SkellyCam` main loop...")

    while True:
        ready_event = multiprocessing.Event()
        reboot_event = multiprocessing.Event()
        shutdown_event = multiprocessing.Event()


        logger.info("Starting backend server process...")

        backend_process, hostname, port = run_backend(timeout=BACKEND_TIMEOUT,
                                                      ready_event=ready_event,
                                                      shutdown_event=shutdown_event)

        logger.info("Starting frontend/client process...")
        frontend_process = run_frontend(hostname=hostname,
                                        port=port,
                                        backend_timeout=BACKEND_TIMEOUT,
                                        reboot_event=reboot_event,
                                        shutdown_event=shutdown_event)

        while frontend_process.is_alive() and backend_process.is_alive():
            logger.trace("Main loop is running happily...")
            time.sleep(5)

        backend_process.terminate()
        frontend_process.terminate()

        if reboot_event.is_set():
            logger.info(f"Rebooting Skelly Cam...")
            continue
        else:
            logger.info(f"Exiting Skelly Cam...")
            break

    shutdown_event.set()
    logger.info("Shutting down...")
    frontend_process.join()
    backend_process.join()

    logger.info("Shut down successfully!")


if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")

    freeze_support()
    setup_app_id_for_windows()

    main_loop()

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")

    logger.success("Done!")
