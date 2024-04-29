import logging
import multiprocessing

from PySide6.QtWidgets import QApplication
from setproctitle import setproctitle

from skellycam.frontend.api_client.api_client import HttpClient
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow

logger = logging.getLogger(__name__)


class SkellyCamQtApplication(QApplication):
    def __init__(
        self,
        hostname: str,
        port: int,
    ):
        logger.info("Initializing SkellyCamQtApplication...")
        super().__init__()

        logger.info("Creating API client...")


        self._main_window = SkellyCamMainWindow(hostname=hostname, port=port)
        self._main_window.show()


    def closingDown(self):
        logger.info("SkellyCamQtApplication is closing down...")
        super().closingDown()
