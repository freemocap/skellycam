import multiprocessing

from skellycam import logger
from skellycam.backend.backend_loop import backend_main_loop
from skellycam.frontend.frontend_loop import frontend_loop


def start_up(exit_event):
    # pretend they are one-way pipes
    messages_from_frontend = multiprocessing.Queue()
    messages_from_backend = multiprocessing.Queue()
    backend_process = start_backend_process(exit_event=exit_event,
                                            messages_from_backend=messages_from_backend,
                                            messages_from_frontend=messages_from_frontend)
    frontend_process, reboot_event = start_frontend_process(exit_event=exit_event,
                                                            messages_from_backend=messages_from_backend,
                                                            messages_from_frontend=messages_from_frontend)
    return backend_process, frontend_process, reboot_event


def reset_events(exit_event, reboot_event):
    logger.debug(f"Resetting `exit_event` and `reboot_event`...")
    exit_event.clear()
    reboot_event.clear()


def start_frontend_process(exit_event: multiprocessing.Event,
                           messages_from_frontend: multiprocessing.Queue,
                           messages_from_backend: multiprocessing.Queue,
                           ):
    logger.info(f"Starting frontend process...")
    reboot_event = multiprocessing.Event()
    frontend_process = multiprocessing.Process(target=frontend_loop, args=(messages_from_frontend,
                                                                           messages_from_backend,
                                                                           exit_event,
                                                                           reboot_event))
    frontend_process.start()
    logger.success(f"Frontend process started!")
    return frontend_process, reboot_event


def start_backend_process(exit_event: multiprocessing.Event,
                          messages_from_frontend: multiprocessing.Queue,
                          messages_from_backend: multiprocessing.Queue):
    logger.info(f"Starting backend process...")
    backend_process = multiprocessing.Process(target=backend_main_loop, args=(messages_from_frontend,
                                                                              messages_from_backend,
                                                                              exit_event))
    backend_process.start()
    logger.success(f"Backend process started!")
    return backend_process


def shut_down(exit_event: multiprocessing.Event, backend_process: multiprocessing.Process,
              frontend_process: multiprocessing.Process):
    logger.info(f"Shutting down frontend and backend processes...")
    exit_event.set()
    backend_process.join()
    frontend_process.join()
    logger.success(f"Frontend and backend processes shut down!")
