import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from fast_camera_capture.controllers.qt_app.controller_main_window import ControllerMainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    win = ControllerMainWindow()
    win.show()
    error_code = app.exec()

    sys.exit()
