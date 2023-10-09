# __main__.py
import logging
import multiprocessing
import time
from multiprocessing import freeze_support

from skellycam.backend.backend_main import backend_main
from skellycam.frontend.frontend_main import frontend_main
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows

from skellycam import logger


def main():
    messages_from_frontend, messages_to_backend = multiprocessing.Pipe(duplex=False)
    messages_from_backend, messages_to_frontend = multiprocessing.Pipe(duplex=False)

    exit_event = multiprocessing.Event()
    reboot_event = multiprocessing.Event()
    reboot_attempt = False
    while not exit_event.is_set() or reboot_attempt:
        backend_process = multiprocessing.Process(target=backend_main, args=(messages_from_frontend,
                                                                             messages_to_frontend,
                                                                             exit_event,
                                                                             reboot_event))
        frontend_process = multiprocessing.Process(target=frontend_main, args=(messages_from_backend,
                                                                               messages_to_backend,
                                                                               exit_event,
                                                                               reboot_event))

        logger.info(f"Starting backend process...")
        backend_process.start()

        logger.info(f"Starting frontend process...")
        frontend_process.start()

        while True:
            time.sleep(1.0)
            if exit_event.is_set():
                logger.info(f"Exit event set, joining processes...")
                backend_process.join()
                frontend_process.join()
                break

            if reboot_event.is_set():
                if reboot_attempt:
                    logger.info(f"Reboot attempt failed, exiting...")
                    exit_event.set()
                    break
                reboot_attempt = True
                exit_event.clear()
                reboot_event.clear()
                logger.info(f"Rebooting...")

    logger.info(f"Exiting main...")

if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")
    freeze_support()
    setup_app_id_for_windows()
    main()
    logger.info(f"Exiting __main__, bye!")

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")
