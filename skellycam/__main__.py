# __main__.py
import multiprocessing
import time
from multiprocessing import freeze_support

from skellycam.api.run_backend import run_backend
from skellycam.system.logging_configuration.configure_logging import (
    configure_logging,
)

from skellycam.system.logging_configuration.log_level_enum import LogLevel

from skellycam.frontend.run_frontend import run_frontend

from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

configure_logging(LogLevel.TRACE)
import logging

logger = logging.getLogger(__name__)


REBOOT_EXIT_CODE = 123  # reboot if exit code is 123

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")

    freeze_support()
    setup_app_id_for_windows()

    while True:
        logger.info("Starting backend server process...")
        ready_event = multiprocessing.Event()

        # Run the backend server
        backend_process, hostname, port = run_backend(ready_event)

        while not ready_event.is_set():
            logger.debug("Waiting for backend server to start...")
            time.sleep(1)

        logger.info(f"Backend server is running on: https://{hostname}:{port}")

        # Run the frontend gui app/client
        exit_code = run_frontend(hostname, port)  # blocks until the frontend exits

        logger.info(f"Frontend ended with exit code: {exit_code}")
        logger.info(f"Shutting down backend/server process")
        backend_process.terminate()

        if exit_code == REBOOT_EXIT_CODE:
            logger.info(f"Rebooting Skelly Cam")
            continue
        else:
            logger.info(f"Exiting Skelly Cam...")
            break

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")

    logger.info("Done!")
