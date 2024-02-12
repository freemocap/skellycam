from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.api_client import ApiClient
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow

_QT_APPLICATION = None


def create_or_recreate_qt_application(
    hostname: str, port: int
) -> "SkellyCamQtApplication":
    global _QT_APPLICATION
    if _QT_APPLICATION is None:
        logger.info(f"Creating QApplication...")
        _QT_APPLICATION = SkellyCamQtApplication(hostname, port)
    else:
        logger.info(f"Recreating QApplication...")
        _QT_APPLICATION.quit()
        _QT_APPLICATION.deleteLater()
        _QT_APPLICATION = SkellyCamQtApplication(hostname, port)
    return _QT_APPLICATION


class SkellyCamQtApplication(QApplication):
    def __init__(self, hostname: str, port: int):
        super().__init__()
        self._backend_hostname = hostname
        self._backend_port = port

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

    def _create_keep_alive_timer(self, interval: int = 10000):
        self._keep_alive_timer = QTimer(self)
        self._keep_alive_timer.timeout.connect(self.websocket_client.send_ping)
        self._keep_alive_timer.start(interval)
