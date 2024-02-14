import logging
import multiprocessing

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from skellycam.frontend.api_client.api_client import ApiClient
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow

logger = logging.getLogger(__name__)


class SkellyCamQtApplication(QApplication):
    def __init__(
        self,
        hostname: str,
        port: int,
        backend_timeout: float,
        reboot_event: multiprocessing.Event,
        shutdown_event: multiprocessing.Event,
    ):
        logger.info("Initializing SkellyCamQtApplication...")
        super().__init__()
        self._construct_urls(hostname, port)
        self._backend_timeout = backend_timeout
        self._reboot_event = reboot_event
        self._shutdown_event = shutdown_event

        self._create_backend_clients()

        self._main_window = SkellyCamMainWindow(self.api_client, self.websocket_client)
        self._main_window.show()

    def _construct_urls(self, hostname, port):
        self._backend_hostname = hostname
        self._backend_port = port
        self._backend_http_url = f"http://{self._backend_hostname}:{self._backend_port}"
        self._backend_websocket_url = (
            f"ws://{self._backend_hostname}:{self._backend_port}/websocket"
        )

    def _create_backend_clients(self):
        logger.info("Creating API client...")
        self.api_client = ApiClient(self._backend_http_url)

        logger.info("Creating WebSocket client...")
        self.websocket_client = FrontendWebsocketClient(self._backend_websocket_url)

    def _create_keep_alive_timer(self):
        self._keep_alive_timer = QTimer(self)
        self._keep_alive_timer.timeout.connect(self._send_keep_alive_ping)

        keep_alive_interval_ms = int((self._backend_timeout / 2) * 1000)
        self._keep_alive_timer.start(keep_alive_interval_ms)

    def _send_keep_alive_ping(self):
        logger.trace("Sending keep-alive ping to backend server...")
        self.websocket_client.send_ping()

    def closingDown(self):
        logger.info("SkellyCamQtApplication is closing down...")
        self._shutdown_event.set()
        super().closingDown()
