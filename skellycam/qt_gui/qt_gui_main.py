import logging
import sys

from skellycam.qt_gui.utilities.get_qt_app import get_qt_app

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QTimer

from skellycam.qt_gui.qt_gui_main_window import QtGUIMainWindow


def qt_gui_main():
    app = get_qt_app(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.



    qt_gui_main_window = QtGUIMainWindow()
    qt_gui_main_window.show()
    error_code = app.exec()



    logger.info(f"Exiting with code: {error_code}")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    sys.exit()



if __name__ == "__main__":
    qt_gui_main()
