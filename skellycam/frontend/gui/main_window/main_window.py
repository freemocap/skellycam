import multiprocessing
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QVBoxLayout

from skellycam.system.environment.get_logger import logger
from skellycam.frontend.gui.css.qt_css_stylesheet import QT_CSS_STYLE_SHEET_STRING
from skellycam.frontend.gui.main_window.keyboard_shortcuts import KeyboardShortcuts
from skellycam.frontend.gui.skellycam_widget.skellycam_widget import SkellyCamWidget
from skellycam.system.environment.default_paths import PATH_TO_SKELLY_CAM_LOGO_PNG


class SkellyCamMainWindow(QMainWindow):

    def __init__(self,
                 exit_event: multiprocessing.Event,
                 reboot_event: multiprocessing.Event,
                 messages_from_frontend: multiprocessing.Queue,
                 messages_from_backend: multiprocessing.Queue,
                 frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection,
                 ):
        logger.info("Initializing QtGUIMainWindow")
        super().__init__()
        self._messages_from_frontend = messages_from_frontend
        self._messages_from_backend = messages_from_backend
        self._frontend_frame_pipe_receiver = frontend_frame_pipe_receiver
        self.shortcuts = KeyboardShortcuts(exit_event=exit_event,
                                           reboot_event=reboot_event)
        self.shortcuts.connect_shortcuts(self)
        self._initUI()

    def _initUI(self):
        self.setGeometry(100, 100, 1600, 900)
        if not Path(PATH_TO_SKELLY_CAM_LOGO_PNG).is_file():
            raise FileNotFoundError(f"Could not find logo at {PATH_TO_SKELLY_CAM_LOGO_PNG}")
        self.setWindowIcon(QIcon(PATH_TO_SKELLY_CAM_LOGO_PNG))
        self.setStyleSheet(QT_CSS_STYLE_SHEET_STRING)
        self.setWindowTitle("Skelly Cam \U0001F480 \U0001F4F8")

        self._layout = QVBoxLayout()
        self.skellycam_widget = SkellyCamWidget(parent=self,
                                                messages_from_frontend=self._messages_from_frontend,
                                                messages_from_backend=self._messages_from_backend,
                                                frontend_frame_pipe_receiver=self._frontend_frame_pipe_receiver,
        )
        self.setCentralWidget(self.skellycam_widget)

    def closeEvent(self, event):
        logger.info("Closing MainWindow...")
        self.shortcuts.quit()
        event.accept()
