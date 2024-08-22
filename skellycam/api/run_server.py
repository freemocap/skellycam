import logging
import multiprocessing
import threading
import time
from typing import Optional

import uvicorn
from uvicorn import Server

APP_FACTORY_PATH = "skellycam.api.app_factory:create_app"

logger = logging.getLogger(__name__)
PROTOCOL = "http"
HOSTNAME = "localhost"
PORT = 8005
APP_URL = f"{PROTOCOL}://{HOSTNAME}:{PORT}"


class UvicornServerManager:
    def __init__(self, hostname: str = HOSTNAME, port: int = PORT, log_level: str = "info"):
        self.hostname: str = hostname
        self.port: int = port
        self.server_thread: Optional[threading.Thread] = None
        self.server: Optional[Server] = None
        self.shutdown_event: threading.Event = threading.Event()

        self.log_level: str = log_level

    @property
    def is_running(self):
        return self.server_thread.is_alive() if self.server_thread else False

    def start_server(self):
        config = uvicorn.Config(
            APP_FACTORY_PATH,
            host=self.hostname,
            port=self.port,
            log_level=0,  # self.log_level,
            reload=True,
            factory=True
        )
        logger.info(f"Starting uvicorn server on {self.hostname}:{self.port}")
        self.server = uvicorn.Server(config)

        def server_thread():
            try:
                self.server.run()
            except Exception as e:
                logger.error(f"A fatal error occurred in the uvicorn server: {e}")
                logger.exception(e)
                raise e
            finally:
                logger.info(f"Shutting down uvicorn server")

        self.server_thread = threading.Thread(target=server_thread)
        self.server_thread.start()

    def shutdown_server(self):
        logger.info("Shutting down Uvicorn Server...")
        if self.server:
            self.server.should_exit = True
            self.server_thread.join()
            logger.info("Uvicorn Server shutdown successfully")


# singleton
UVICORN_SERVER_MANAGER = None


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
