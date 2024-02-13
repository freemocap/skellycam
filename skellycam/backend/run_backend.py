import multiprocessing
import time
from multiprocessing import Process
from typing import Tuple

from PySide6.QtCore import QTimer

from skellycam.backend.api_server.find_available_port import find_available_port
from skellycam.backend.api_server.run_uvicorn_server import run_uvicorn_server
import logging


def run_backend(
    ready_event: multiprocessing.Event,
    shutdown_event: multiprocessing.Event,
    timeout: float,
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

    backend_process = Process(
        target=run_uvicorn_server,
        args=(hostname, port, ready_event, shutdown_event, timeout),
    )
    backend_process.start()

    while not ready_event.is_set():
        logger.debug("Waiting for backend server to start...")
        time.sleep(1)

    logger.info(f"Backend server is running on: https://{hostname}:{port}")

    if backend_process.is_alive():
        logger.info(f"Backend server started on port {port}.")
        return backend_process, hostname, port

    raise Exception(f"Backend server failed to start on port {port} :(")


logger = logging.getLogger(__name__)


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

    backend_process_out, localhost_outer, port_outer = run_backend()
    print(f"Backend server is running on: http://{localhost_outer}:{port_outer}")
    ws_url_outer = f"ws://{localhost_outer}:{port_outer}/websocket"
    app = SimpleApp(ws_url_outer)
    app.exec()
    logger.info(f"Done!")
