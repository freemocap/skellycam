import logging
import multiprocessing
import time

from skellycam.api.server.server_manager import get_server_manager

logger = logging.getLogger(__name__)


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
