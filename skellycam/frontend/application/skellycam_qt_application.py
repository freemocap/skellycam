import logging
import multiprocessing

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from skellycam.frontend.api_client.api_client import ApiClient
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow

logger = logging.getLogger(__name__)

_QT_APPLICATION = None


def create_or_recreate_qt_application(
    hostname: str,
    port: int,
    backend_timeout: float,
    reboot_event: multiprocessing.Event,
    shutdown_event: multiprocessing.Event,
) -> "SkellyCamQtApplication":
    global _QT_APPLICATION

    def _delete_qt_application():
        if _QT_APPLICATION is not None:
            _QT_APPLICATION.quit()
            _QT_APPLICATION.deleteLater()

    def _create_qt_application():
        return SkellyCamQtApplication(
            hostname=hostname,
            port=port,
            backend_timeout=backend_timeout,
            reboot_event=reboot_event,
            shutdown_event=shutdown_event,
        )

    if _QT_APPLICATION is None:
        logger.info(f"Creating QApplication...")
        _QT_APPLICATION = _create_qt_application()

    else:
        logger.info(f"Recreating QApplication...")
        _delete_qt_application()
        _QT_APPLICATION = _create_qt_application()

    return _QT_APPLICATION


class SkellyCamQtApplication(QApplication):
    def __init__(
        self,
        hostname: str,
        port: int,
        backend_timeout: float,
        reboot_event: multiprocessing.Event,
        shutdown_event: multiprocessing.Event,
    ):
        super().__init__()
        self._backend_hostname = hostname
        self._backend_port = port
        self._backend_timeout = backend_timeout
        self._reboot_event = reboot_event
        self._shutdown_event = shutdown_event

        self._create_backend_clients(self._backend_hostname, self._backend_port)

        self._main_window = SkellyCamMainWindow(self.api_client, self.websocket_client)
        self._main_window.show()

    def _create_backend_clients(self, hostname: str, port: int):
        self._create_api_client()
        self._create_websocket_client()

    def _create_websocket_client(self):
        self._backend_websocket_url = (
            f"ws://{self._backend_hostname}:{self._backend_port}/websocket"
        )
        self.websocket_client = FrontendWebsocketClient(self._backend_websocket_url)

    def _create_api_client(self):
        self._backend_http_url = f"http://{self._backend_hostname}:{self._backend_port}"
        self.api_client = ApiClient(self._backend_http_url)

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
