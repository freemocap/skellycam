import logging
import multiprocessing
import time

from skellycam.backend.run_backend import run_backend
from skellycam.frontend.run_frontend import run_frontend

logger = logging.getLogger(__name__)

BACKEND_TIMEOUT = 30


def main_loop():
    logger.info("Starting `SkellyCam` main loop...")
    try:
        while True:

            backend_process, frontend_process = create_sub_processes()

            while frontend_process.is_alive() and backend_process.is_alive():
                logger.trace("Main loop is running happily...")
                time.sleep(5)
            else:
                logger.info(f"Exiting Skelly Cam...")
                break
    except Exception as e:
        logger.error(f"A fatal error occurred in the main loop: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info("Cleaning up resources and shutting down...")

    logger.info("Shut down successfully!")

    logger.info("Shutting down...")

    terminate_all_processes()

    logger.info("Shut down successfully!")


def terminate_all_processes() -> None:
    logger.info("Terminating any active sub-processes...")
    for process in multiprocessing.active_children():
        if process.is_alive():
            logger.debug(f"Terminating process {process.name}...")
        process.terminate()


def create_sub_processes():
    logger.info("Starting backend process...")
    backend_process, hostname, port = run_backend()
    logger.info("Starting frontend process...")
    frontend_process = run_frontend(
        hostname=hostname,
        port=port)

    return backend_process, frontend_process


if __name__ == "__main__":
    raise Exception(
        "This file is not meant to be run directly - please run `__main__.py` instead :) "
    )
