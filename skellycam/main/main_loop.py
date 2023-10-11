import multiprocessing
import time

from skellycam import logger
from skellycam.backend.backend_main import backend_main_loop
from skellycam.frontend.frontend_main import frontend_main_loop


def main():
    logger.info(f"Starting main...")

    exit_event = multiprocessing.Event()

    while not exit_event.is_set():

        backend_process, frontend_process, reboot_event = start_up(exit_event)

        while True:
            time.sleep(1.0)
            # logger.trace(f"Checking for exit or reboot events...")
            if exit_event.is_set() or reboot_event.is_set():
                logger.info(f"Exit event set, joining processes and wait for them to shut down...")
                shut_down(exit_event=exit_event,
                          backend_process=backend_process,
                          frontend_process=frontend_process)
                if reboot_event.is_set():
                    reset_events(exit_event, reboot_event)
                    logger.info(f"Rebooting...")
                    break

                break

    logger.info(f"Exiting main...")
