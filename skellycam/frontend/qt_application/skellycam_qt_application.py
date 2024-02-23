import logging
import multiprocessing

from PySide6.QtWidgets import QApplication

from skellycam.frontend.api_client.api_client import ApiClient
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

        logger.info("Creating API client...")
        self.api_client = ApiClient(self._backend_http_url)

        self._main_window = SkellyCamMainWindow(self.api_client)
        self._main_window.show()

    def _construct_urls(self, hostname, port):
        self._backend_hostname = hostname
        self._backend_port = port
        self._backend_http_url = f"http://{self._backend_hostname}:{self._backend_port}"

    def closingDown(self):
        logger.info("SkellyCamQtApplication is closing down...")
        self._shutdown_event.set()
        super().closingDown()
