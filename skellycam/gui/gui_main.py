import logging
import sys

from PySide6.QtCore import QTimer

from skellycam.gui.qt.skelly_cam_main_window import SkellyCamMainWindow
from skellycam.gui.qt.utilities.get_qt_app import get_qt_app

logger = logging.getLogger(__name__)


def gui_main(shutdown_event=None):
    logger.info("Starting GUI main...")

    qt_app = get_qt_app(sys.argv)
    main_window = SkellyCamMainWindow(shutdown_event=shutdown_event)
    main_window.show()

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: main_window.update_widget())  # Update the main window once per second

    logger.success("GUI main window presumably opened")
    error_code = qt_app.exec()  # Will block until the GUI window is closed

    logger.info(f"Exiting with code: {error_code}")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    sys.exit()


if __name__ == "__main__":
    gui_main()
