import multiprocessing
from multiprocessing import Event

from skellycam import logger
from skellycam.backend.backend_loop import backend_loop

CONTROLLER = None


def backend_main(messages_from_frontend: multiprocessing.Queue,
                 messages_from_backend: multiprocessing.Queue,
                 exit_event: Event):
    logger.success(f"Backend main started!")
    backend_loop(exit_event=exit_event,
                 messages_from_backend=messages_from_backend,
                 messages_from_frontend=messages_from_frontend)

    if not exit_event.is_set():
        logger.info(f"SETTING EXIT EVENT")
        exit_event.set()


