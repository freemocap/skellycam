import logging
import sys
from PySide6.QtCore import QTimer

from skellycam.gui.qt.skelly_cam_main_window import SkellyCamMainWindow
from skellycam.gui.qt.utilities.get_qt_app import get_qt_app

logger = logging.getLogger(__name__)


def qt_gui_main():
    app = get_qt_app(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    main_window = SkellyCamMainWindow()
    main_window.show()
    error_code = app.exec()

    logger.info(f"Exiting with code: {error_code}")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    sys.exit()


if __name__ == "__main__":
    qt_gui_main()
