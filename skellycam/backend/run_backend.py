import logging
from multiprocessing import Process
from typing import Tuple

from skellycam.backend.api.app.find_available_port import find_available_port
from skellycam.backend.api.app.server import run_uvicorn_server

logger = logging.getLogger(__name__)


def run_backend(
        hostname: str = "localhost",
        preferred_port: int = 8003,
) -> Tuple[Process, str, int]:
    port = find_available_port(preferred_port)

    backend_process = Process(
        target=run_uvicorn_server,
        args=(hostname, port),
    )
    backend_process.start()

    if backend_process.is_alive():
        logger.info(f"Backend server started on port {port}")
        return backend_process, hostname, port

    raise Exception(f"Backend server failed to start on port {port} :(")


if __name__ == "__main__":

    logger.info("Running script app")
    run_backend()
