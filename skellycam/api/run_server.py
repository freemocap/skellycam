import socket
from typing import Tuple

import uvicorn

from skellycam.api.fastapi_app import FastApiApp
from skellycam.backend.system.environment.get_logger import logger
from multiprocessing import Process


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


def run_backend() -> Tuple[Process, str]:
    hostname = "localhost"
    port = find_available_port(8000)

    backend_process = Process(target=run_backend_api_server, args=(hostname, port))
    backend_process.start()
    if backend_process.is_alive():
        logger.info(f"Backend server started on port {port}.")
        api_location = f"http://{hostname}:{port}"
        return backend_process, api_location

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
    backend_process_out, api_location_out = run_backend()
    print(f"Backend server is running on: {api_location_out}")
    backend_process_out.join()
    logger.info(f"Done!")
