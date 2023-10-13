import multiprocessing
import time

from skellycam import logger
from skellycam.main.helpers import shut_down, reset_events, start_up


def main_process():
    logger.info(f"Starting main...")

    exit_event = multiprocessing.Event()

    main_loop(exit_event)

    logger.info(f"Exiting main...")


def main_loop(exit_event):
    while not exit_event.is_set():
        backend_process, frontend_process, reboot_event = start_up(exit_event)
        try:
            while True:

                time.sleep(1.0)
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
        except Exception as e:
            logger.error(f"An error occurred in Main Loop: {e}")
            logger.exception(e)
            raise e
        finally:
            logger.info(f"Exiting main loop...")
            if not exit_event.is_set():
                logger.info(f"SETTING EXIT EVENT")
                exit_event.set()
