import multiprocessing
import time

from skellycam.api.server.server_manager import UvicornServerManager

UVICORN_SERVER_MANAGER = None
import logging

logger = logging.getLogger(__name__)


def get_server_manager(*args, **kwargs) -> UvicornServerManager:
    global UVICORN_SERVER_MANAGER
    if UVICORN_SERVER_MANAGER is None:
        UVICORN_SERVER_MANAGER = UvicornServerManager(*args, **kwargs)
    return UVICORN_SERVER_MANAGER


def run_server(shutdown_event: multiprocessing.Event = None):
    server_manager = get_server_manager()
    server_manager.start_server()
    while server_manager.is_running:
        time.sleep(1)
        if shutdown_event and shutdown_event.is_set():
            server_manager.shutdown_server()
            break

    logger.info("Server main process ended")


if __name__ == "__main__":
    run_server()
    print("Done!")
