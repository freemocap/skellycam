import logging
import multiprocessing
import time

from skellycam.api.server.server_singleton import create_server_manager

logger = logging.getLogger(__name__)


def run_server(global_kill_flag: multiprocessing.Value):
    server_manager = create_server_manager(kill_event=kill_event)
    server_manager.start_server()
    while server_manager.is_running:
        time.sleep(1)
        if kill_event.is_set():
            server_manager.shutdown_server()
            break

    logger.info("Server main process ended")


if __name__ == "__main__":
    run_server(multiprocessing.Event())
    print("Done!")
