import logging
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QVBoxLayout

from skellycam.system.default_paths import (
    PATH_TO_SKELLY_CAM_LOGO_PNG,
)

logger = logging.getLogger(__name__)
from skellycam.frontend.clients.http_client import HttpClient
from skellycam.frontend.gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.frontend.gui.skellycam_widget.skellycam_widget import SkellyCamWidget


class SkellyCamMainWindow(QMainWindow):
    def __init__(self, hostname: str, port: int):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()
        # self.shortcuts = KeyboardShortcuts()
        # self.shortcuts.connect_shortcuts(self)
        self._initUI(hostname, port)

    def _initUI(self, hostname: str, port: int):
        self.setGeometry(100, 100, 1600, 900)
        if not Path(PATH_TO_SKELLY_CAM_LOGO_PNG).is_file():
            raise FileNotFoundError(
                f"Could not find logo at {PATH_TO_SKELLY_CAM_LOGO_PNG}"
            )
        self.setWindowIcon(QIcon(PATH_TO_SKELLY_CAM_LOGO_PNG))
        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)
        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")

        self._layout = QVBoxLayout()
        self.skellycam_widget = SkellyCamWidget(
            parent=self,
            hostname=hostname,
            port=port,
        )
        self.setCentralWidget(self.skellycam_widget)

    def closeEvent(self, event):
        logger.info("Closing MainWindow...")
        event.accept()
