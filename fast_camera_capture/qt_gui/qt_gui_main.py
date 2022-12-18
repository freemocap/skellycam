import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from fast_camera_capture.qt_gui.qt_gui_main_window import QtGUIMainWindow
from fast_camera_capture.system.environment.default_paths import default_session_folder_path

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.
    session_folder_path = default_session_folder_path(create_folder=True)
    qt_gui_main_window = QtGUIMainWindow(session_folder_path=session_folder_path)
    qt_gui_main_window.show()
    error_code = app.exec()

    if not any(Path(session_folder_path).iterdir()):
        logger.info(f"Session folder: {session_folder_path} is empty, deleting it")
        Path(session_folder_path).rmdir()

    sys.exit()
