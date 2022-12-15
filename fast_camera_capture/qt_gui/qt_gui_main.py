import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from fast_camera_capture.qt_gui.qt_gui_main_window import QtGUIMainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    win = QtGUIMainWindow()
    win.show()
    error_code = app.exec()

    sys.exit()
