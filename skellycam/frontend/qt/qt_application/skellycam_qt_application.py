import logging

from PySide6.QtWidgets import QApplication

from skellycam.frontend.qt.gui.main_window.main_window import SkellyCamMainWindow

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
