import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from fast_camera_capture.opencv.viewer.qt_app.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    win = MainWindow()
    win.show()
    error_code = app.exec()

    sys.exit()
