import logging
import multiprocessing
import time

from skellycam.backend.run_backend import run_backend
from skellycam.frontend.run_frontend import run_frontend

logger = logging.getLogger(__name__)

BACKEND_TIMEOUT = 30


def main_loop():
    logger.info("Starting `SkellyCam` main loop...")
    frontend_process = None
    backend_process = None
    shutdown_event = None
    try:
        while True:
            ready_event = multiprocessing.Event()
            reboot_event = multiprocessing.Event()
            shutdown_event = multiprocessing.Event()

            backend_process, frontend_process = create_sub_processes(
                ready_event=ready_event,
                reboot_event=reboot_event,
                shutdown_event=shutdown_event,
            )

            while frontend_process.is_alive() and backend_process.is_alive():
                logger.trace("Main loop is running happily...")
                time.sleep(5)

            if reboot_event.is_set():
                logger.info(f"Rebooting Skelly Cam...")
                continue
            else:
                logger.info(f"Exiting Skelly Cam...")
                break
    except Exception as e:
        logger.error(f"A fatal error occurred in the main loop: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info("Cleaning up resources and shutting down...")
        if shutdown_event is not None:
            shutdown_event.set()

        if frontend_process is not None:
            if frontend_process.is_alive():
                frontend_process.terminate()
                frontend_process.join(timeout=5)

        if backend_process is not None:
            if backend_process.is_alive():
                backend_process.terminate()
                backend_process.join(timeout=5)

        if frontend_process.is_alive() or backend_process.is_alive():
            logger.error("Failed to cleanly shutdown all processes")

    logger.info("Shut down successfully!")

    shutdown_event.set()
    logger.info("Shutting down...")
    frontend_process.join()
    backend_process.join()

    logger.info("Shut down successfully!")


def create_sub_processes(
    ready_event: multiprocessing.Event,
    reboot_event: multiprocessing.Event,
    shutdown_event: multiprocessing.Event,
):
    logger.info("Starting backend process...")
    backend_process, hostname, port = run_backend(
        timeout=BACKEND_TIMEOUT,
        ready_event=ready_event,
        shutdown_event=shutdown_event,
    )
    logger.info("Starting frontend process...")
    frontend_process = run_frontend(
        hostname=hostname,
        port=port,
        backend_timeout=BACKEND_TIMEOUT,
        reboot_event=reboot_event,
        shutdown_event=shutdown_event,
    )

    return backend_process, frontend_process


if __name__ == "__main__":
    raise Exception(
        "This file is not meant to be run directly - please run `__main__.py` instead."
    )
