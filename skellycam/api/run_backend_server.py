import socket
from multiprocessing import Process
from typing import Tuple

import uvicorn
from PySide6.QtCore import QTimer

from fastapi.routing import APIRoute
from starlette.routing import WebSocketRoute

from skellycam.api.fastapi_app import FastApiApp
from skellycam.backend.system.environment.get_logger import logger


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
    log_api_routes(app, hostname, port)
    uvicorn.run(
        app,
        host=hostname,
        port=port,
        log_level="debug"
        # reload=True
    )


def log_api_routes(app, hostname, port):
    debug_string = f"Starting Uvicorn server on {hostname}:{port} serving routes:\n\n "
    api_routes = ""
    websocket_routes = ""
    for route in app.routes:
        if isinstance(route, APIRoute):
            api_routes += (
                f"name: {route.name}, path: {route.path}, methods: {route.methods}\n"
            )

        elif isinstance(route, WebSocketRoute):
            websocket_routes += f"name: {route.name}, path: {route.path}"
    debug_string += f"HTTP routes: \n{api_routes}\n Websockets: \n{websocket_routes}\n"
    logger.info(debug_string)


if __name__ == "__main__":
    from skellycam.experiments.simple_websocket import SimpleWebSocketClient
    from PySide6.QtWidgets import QPushButton, QApplication

    class SimpleApp(QApplication):
        def __init__(self, ws_url: str):
            super().__init__()
            self.client = SimpleWebSocketClient(ws_url)
            self.main_window = QPushButton("Send Ping")
            self.main_window.clicked.connect(self.client.send_ping)
            self.main_window.show()
            self.beep_timer = QTimer(self)
            self.beep_timer.timeout.connect(self.client.send_beep)
            self.beep_timer.start(1000)  # Set interval in milliseconds

    backend_process_out, localhost, port = run_backend()
    print(f"Backend server is running on: http://{localhost}:{port}")
    ws_url_outer = f"ws://{localhost}:{port}/websocket"
    app = SimpleApp(ws_url_outer)
    app.exec()
    logger.info(f"Done!")
