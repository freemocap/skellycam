import multiprocessing
from multiprocessing import Event

from skellycam.backend.backend_loop import backend_loop
from skellycam.system.environment.get_logger import logger
from skellycam.utilities.clean_up import remove_empty_directories

CONTROLLER = None


def backend_main(messages_from_frontend: multiprocessing.Queue,
                 messages_from_backend: multiprocessing.Queue,
                 frontend_frame_pipe_sender,  # multiprocessing.connection.Connection
                 exit_event: Event):
    logger.success(f"Backend main started!")
    backend_loop(exit_event=exit_event,
                 frontend_frame_pipe_sender=frontend_frame_pipe_sender,
                 messages_from_backend=messages_from_backend,
                 messages_from_frontend=messages_from_frontend)

    if not exit_event.is_set():
        logger.info(f"SETTING EXIT EVENT")
        exit_event.set()

    remove_empty_directories()
    logger.success(f"Backend main exiting!")
