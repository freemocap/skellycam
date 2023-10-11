# __main__.py
import multiprocessing
import time
from multiprocessing import freeze_support

from skellycam import logger
from skellycam.backend.backend_main import backend_main
from skellycam.frontend.frontend_main import frontend_main
from skellycam.utilities.setup_windows_app_id import setup_app_id_for_windows


def main():
    logger.info(f"Starting main...")

    exit_event = multiprocessing.Event()

    while not exit_event.is_set():
        messages_from_frontend, messages_to_backend = multiprocessing.Pipe(duplex=False)
        messages_from_backend, messages_to_frontend = multiprocessing.Pipe(duplex=False)

        backend_process = start_backend_process(exit_event, messages_from_frontend, messages_to_frontend)
        frontend_process, reboot_event = start_frontend_process(exit_event, messages_from_backend, messages_to_backend)

        while True:
            time.sleep(1.0)
            if exit_event.is_set() or reboot_event.is_set():
                logger.info(f"Exit event set, joining processes and wait for them to shut down...")
                shut_down(backend_process, exit_event, frontend_process)

            if reboot_event.is_set():
                reset_events(exit_event, reboot_event)
                logger.info(f"Rebooting...")
                break

    logger.info(f"Exiting main...")


def reset_events(exit_event, reboot_event):
    logger.debug(f"Resetting `exit_event` and `reboot_event`...")
    exit_event.clear()
    reboot_event.clear()


def start_frontend_process(exit_event, messages_from_backend, messages_to_backend):
    logger.info(f"Starting frontend process...")
    reboot_event = multiprocessing.Event()
    frontend_process = multiprocessing.Process(target=frontend_main, args=(messages_from_backend,
                                                                           messages_to_backend,
                                                                           exit_event,
                                                                           reboot_event))
    frontend_process.start()
    logger.success(f"Frontend process started!")
    return frontend_process, reboot_event


def start_backend_process(exit_event, messages_from_frontend, messages_to_frontend):
    logger.info(f"Starting backend process...")
    backend_process = multiprocessing.Process(target=backend_main, args=(messages_from_frontend,
                                                                         messages_to_frontend,
                                                                         exit_event))
    backend_process.start()
    logger.success(f"Backend process started!")
    return backend_process


def shut_down(backend_process, exit_event, frontend_process):
    logger.info(f"Shutting down frontend and backend processes...")
    exit_event.set()
    backend_process.join()
    frontend_process.join()
    logger.success(f"Frontend and backend processes shut down!")


if __name__ == "__main__":
    logger.info(f"Running from __main__: {__name__} - {__file__}")
    freeze_support()
    setup_app_id_for_windows()
    main()
    logger.info(f"Exiting __main__, bye!")

    print("\n--------------------------------------------------")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    print("--------------------------------------------------\n")
