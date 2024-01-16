import socket
from multiprocessing import Process
from typing import Tuple

import uvicorn

from skellycam.api.fastapi_app import FastApiApp
from skellycam.backend.system.environment.get_logger import logger
from skellycam.api.frontend_client.get_or_create_api_client import (
    create_api_client,
)


def find_available_port(start_port):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except socket.error as e:
                print(f"Port {port} is in use.")
                port += 1
                if port > 65535:  # No more ports available
                    raise e


def run_backend(
    hostname: str = "localhost",
    preferred_port: int = 8000,
    fail_if_blocked: bool = False,
) -> Tuple[Process, str, int]:
    port = find_available_port(preferred_port)

    if fail_if_blocked and port != preferred_port:
        logger.error(
            f"Preferred port {port} is blocked  and `fail_if_blocked` is True, so I guess I'll die"
        )
        Exception(f"Preferred port ({preferred_port}) was blocked!")

    backend_process = Process(target=run_backend_api_server, args=(hostname, port))
    backend_process.start()
    if backend_process.is_alive():
        logger.info(f"Backend server started on port {port}.")
        return backend_process, hostname, port

    raise Exception(f"Backend server failed to start on port {port} :(")


def run_backend_api_server(hostname: str, port: int):
    app = FastApiApp().app
    uvicorn.run(
        app,
        host=hostname,
        port=port,
        # reload=True
    )


if __name__ == "__main__":
    backend_process_out, localhost, port = run_backend()
    print(f"Backend server is running on: http://{localhost}:{port}")
    backend_process_out.join()
    logger.info(f"Done!")
