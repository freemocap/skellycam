import logging
import multiprocessing
import sys

from PySide6.QtCore import QTimer

from skellycam.gui.qt.skellycam_main_window import SkellyCamMainWindow
from skellycam.gui.qt.utilities.get_qt_app import get_qt_app

logger = logging.getLogger(__name__)


def gui_main(global_kill_flag: multiprocessing.Value) -> None:
    try:
        logger.info("Starting GUI main...")

        qt_app = get_qt_app(sys.argv)
        main_window = SkellyCamMainWindow(global_kill_flag=global_kill_flag)
        main_window.show()

        timer = QTimer()
        timer.start(1000)
        timer.timeout.connect(lambda: main_window.check_if_should_close())  # Update the main window once per second

        logger.success("GUI main window presumably opened")
        error_code = qt_app.exec()  # Will block until the GUI window is closed

        logger.info(f"Exiting with code: {error_code}")
        print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
        sys.exit(error_code)
    except Exception as e:
        logger.exception(f"Error in GUI main: {e}")
        global_kill_flag.value = True
        sys.exit(1)

if __name__ == "__main__":
    gui_main(multiprocessing.Value("b", False))
