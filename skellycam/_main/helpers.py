import multiprocessing
from typing import Tuple

from skellycam.system.environment.get_logger import logger
from skellycam.backend.backend_main import backend_main
from skellycam.frontend.frontend_main import frontend_main


def start_up(exit_event):
    # pretend they are one-way pipes
    frontend_frame_pipe_receiver, frontend_frame_pipe_sender, messages_from_backend, messages_from_frontend = create_queues_and_pipes()

    backend_process = start_backend_process(exit_event=exit_event,
                                            messages_from_backend=messages_from_backend,
                                            messages_from_frontend=messages_from_frontend,
                                            frontend_frame_pipe_sender=frontend_frame_pipe_sender)

    frontend_process, reboot_event = start_frontend_process(exit_event=exit_event,
                                                            messages_from_backend=messages_from_backend,
                                                            messages_from_frontend=messages_from_frontend,
                                                            frontend_frame_pipe_receiver=frontend_frame_pipe_receiver)

    return backend_process, frontend_process, reboot_event, messages_from_frontend, messages_from_backend


def create_queues_and_pipes():
    messages_from_frontend = multiprocessing.Queue()
    messages_from_backend = multiprocessing.Queue()
    frontend_frame_pipe_receiver, frontend_frame_pipe_sender = multiprocessing.Pipe(duplex=False)
    return frontend_frame_pipe_receiver, frontend_frame_pipe_sender, messages_from_backend, messages_from_frontend


def reset_events(exit_event, reboot_event):
    logger.debug(f"Resetting `exit_event` and `reboot_event`...")
    exit_event.clear()
    reboot_event.clear()


def start_frontend_process(exit_event: multiprocessing.Event,
                           messages_from_frontend: multiprocessing.Queue,
                           messages_from_backend: multiprocessing.Queue,
                           frontend_frame_pipe_receiver  # multiprocessing.connection.Connection
                           ) -> Tuple[multiprocessing.Process, multiprocessing.Event]:
    logger.info(f"Starting frontend process...")
    reboot_event = multiprocessing.Event()
    frontend_process = multiprocessing.Process(target=frontend_main,
                                               args=(messages_from_frontend,
                                                     messages_from_backend,
                                                     frontend_frame_pipe_receiver,
                                                     exit_event,
                                                     reboot_event))
    frontend_process.start()
    logger.success(f"Frontend process started!")
    return frontend_process, reboot_event


def start_backend_process(exit_event: multiprocessing.Event,
                          messages_from_frontend: multiprocessing.Queue,
                          messages_from_backend: multiprocessing.Queue,
                          frontend_frame_pipe_sender  # multiprocessing.connection.Connection
                          ) -> multiprocessing.Process:
    logger.info(f"Starting backend process...")
    backend_process = multiprocessing.Process(target=backend_main,
                                              args=(messages_from_frontend,
                                                    messages_from_backend,
                                                    frontend_frame_pipe_sender,
                                                    exit_event))
    backend_process.start()
    logger.success(f"Backend process started!")
    return backend_process


def shut_down(exit_event: multiprocessing.Event,
              backend_process: multiprocessing.Process,
              frontend_process: multiprocessing.Process):
    logger.info(f"Shutting down frontend and backend processes...")
    exit_event.set()
    backend_process.join()
    frontend_process.join()
    logger.success(f"Frontend and backend processes shut down!")
