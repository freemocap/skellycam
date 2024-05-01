import logging
from multiprocessing import Process
from typing import Tuple

from setproctitle import setproctitle

from skellycam.backend.api.app.find_available_port import find_available_port
from skellycam.backend.api.app.run_server import run_uvicorn_server

logger = logging.getLogger(__name__)


def run_backend(
        hostname: str = "localhost",
        preferred_port: int = 8003,
        fail_if_port_unavailable: bool = True,
) -> Tuple[Process, str, int]:

    port = find_available_port(preferred_port)

    if fail_if_port_unavailable and port != preferred_port:
        raise Exception(f"Port {preferred_port} is not available")

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
    process_name = f"Backend{find_available_port(8003)}"
    setproctitle(process_name)
    logger.info("Running script app")
    run_backend()
