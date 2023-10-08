import logging
import multiprocessing.connection
import sys
import time
from typing import Dict, Any

from skellycam.frontend.qt.skelly_cam_main_window import SkellyCamMainWindow
# from skellycam.frontend.qt.skelly_cam_main_window import SkellyCamMainWindow
from skellycam.frontend.qt.utilities.app_singletons.get_or_create_app_state import get_or_create_app_state
from skellycam.frontend.qt.utilities.app_singletons.get_or_create_qt_app import get_or_create_qt_app

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QTimer


def frontend_main(messages_from_backend: multiprocessing.connection.Connection,
                  messages_to_backend: multiprocessing.connection.Connection):

    logger.success(f"Frontend main started!")
    try:
        app = get_or_create_qt_app(sys.argv)
        timer = QTimer()
        timer.start(500)
        timer.timeout.connect(lambda: update())  # Let the interpreter run each 500 ms.

        last_update = time.perf_counter()

        def update(app_state: Dict[str, Any] = get_or_create_app_state()):
            nonlocal last_update

            current_time = time.perf_counter()
            time_elapsed = current_time - last_update
            last_update = current_time
            logger.info(f"Frontend update called- time_elapsed: {time_elapsed}")
            messages_to_backend.send(app_state)
            if messages_from_backend.poll():
                message = messages_from_backend.recv()
                logger.info(f"frontend_main received message from backend: {message}")


        main_window = SkellyCamMainWindow()
        main_window.show()
        error_code = app.exec()
        logger.info(f"Exiting with code: {error_code}")
        print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
        sys.exit()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        messages_to_backend.send({"type": "error",
                                  "message": str(e),
                                  "data": {}})
        sys.exit(1)
