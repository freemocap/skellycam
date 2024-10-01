import logging
import multiprocessing
import threading
import time
from typing import Optional

import uvicorn
from uvicorn import Server

from skellycam.api.app.create_app import create_app
from skellycam.api.server.server_constants import HOSTNAME, PORT
from skellycam.api.server.server_kill_event import set_kill_event
from skellycam.utilities.kill_process_on_port import kill_process_on_port

logger = logging.getLogger(__name__)


class UvicornServerManager:
    def __init__(self,
                 kill_event:multiprocessing.Event,
                 hostname: str = HOSTNAME,
                 port: int = PORT,
                 log_level: str = "info"):
        self._kill_event = kill_event
        set_kill_event(kill_event)
        self.hostname: str = hostname
        self.port: int = port
        self.server_thread: Optional[threading.Thread] = None
        self.server: Optional[Server] = None
        self.log_level: str = log_level

    @property
    def is_running(self):
        return self.server_thread.is_alive() if self.server_thread else False

    def start_server(self):

        config = uvicorn.Config(
            create_app,
            host=self.hostname,
            port=self.port,
            log_level=0,  # self.log_level,
            reload=True,
            factory=True
        )

        logger.info(f"Starting uvicorn server on {self.hostname}:{self.port}")
        kill_process_on_port(port=self.port)
        self.server = uvicorn.Server(config)

        def server_thread():
            try:
                self.server.run()
            except Exception as e:
                logger.error(f"A fatal error occurred in the uvicorn server: {e}")
                logger.exception(e)
                raise
            finally:
                logger.info(f"Shutting down uvicorn server")

        self.server_thread = threading.Thread(target=server_thread)
        self.server_thread.start()

    def shutdown_server(self):
        logger.info("Shutting down Uvicorn Server...")
        if self.server:
            self._kill_event.set()
            self.server.should_exit = True
            self.server.shutdown()
            waiting_time = 0
            while self.server_thread.is_alive():
                waiting_time += 1
                time.sleep(1)
                if waiting_time > 10:
                    logger.debug("Server thread is not shutting down. Forcing exit...")
                    self.server.force_exit = True

            logger.info("Uvicorn Server shutdown successfully")


UVICORN_SERVER_MANAGER = None


def get_server_manager(kill_event:multiprocessing.Event, *args, **kwargs) -> UvicornServerManager:
    global UVICORN_SERVER_MANAGER
    if UVICORN_SERVER_MANAGER is None:
        UVICORN_SERVER_MANAGER = UvicornServerManager(kill_event, *args, **kwargs)
    return UVICORN_SERVER_MANAGER
