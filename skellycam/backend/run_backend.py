import logging
import multiprocessing
import time
from multiprocessing import Process
from typing import Tuple

from skellycam.backend.api.utilities.find_available_port import find_available_port
from skellycam.backend.api.app.app_factory import run_uvicorn_server

logger = logging.getLogger(__name__)


def run_backend(
        ready_event: multiprocessing.Event = multiprocessing.Event(),
        shutdown_event: multiprocessing.Event = multiprocessing.Event(),
        timeout: float = 30,
        hostname: str = "localhost",
        preferred_port: int = 8000,
        fail_if_blocked: bool = False,
) -> Tuple[Process, str, int]:
    logger.info(
        f"Starting backend server with hostname: `{hostname}` on port: `{preferred_port}`"
    )

    port = find_available_port(preferred_port)

    if fail_if_blocked and port != preferred_port:
        logger.error(
            f"Preferred port {port} is blocked  and `fail_if_blocked` is True, so I guess I'll die"
        )
        Exception(f"Preferred port ({preferred_port}) was blocked!")

    backend_process = Process(
        target=run_uvicorn_server,
        args=(hostname, port),
    )
    backend_process.start()

    while not ready_event.is_set():
        logger.debug("Waiting for backend server to start...")
        time.sleep(1)

    logger.info(
        f"Backend server is running with hostname: `{hostname}` on port: `{port}`"
    )

    if backend_process.is_alive():
        logger.info(f"Backend server started on port {port}.")
        return backend_process, hostname, port

    raise Exception(f"Backend server failed to start on port {port} :(")


if __name__ == "__main__":
    from skellycam.system.logging_configuration.configure_logging import configure_logging
    configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("Running script app")
    run_backend()
