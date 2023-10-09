import logging
import multiprocessing.connection
import sys
import time

from PySide6.QtCore import QTimer

from skellycam.frontend.app_state.app_singletons.get_or_create_app_state_manager import get_or_create_app_state_manager
from skellycam.frontend.app_state.app_singletons.get_or_create_qt_app import get_or_create_qt_app
from skellycam.frontend.app_state.app_state_manager import AppStateManager
from skellycam.frontend.qt.skelly_cam_main_window import SkellyCamMainWindow

frontend_logger = logging.getLogger(__name__)


def frontend_main(messages_from_backend: multiprocessing.connection.Connection,
                  messages_to_backend: multiprocessing.connection.Connection,
                  exit_event: multiprocessing.Event):
    error_code = 0
    while not exit_event.is_set():
        frontend_logger.success(f"Frontend main started!")
        try:
            app = get_or_create_qt_app(sys.argv)
            app_state_manager = get_or_create_app_state_manager()
            timer = QTimer()
            timer.start(500)
            timer.timeout.connect(lambda: update())  # Let the interpreter run each 500 ms.
            last_update = time.perf_counter()

            def update(app_state_manager: AppStateManager = app_state_manager):
                nonlocal last_update

                current_time = time.perf_counter()
                time_elapsed = current_time - last_update
                last_update = current_time
                frontend_logger.info(f"Frontend update called- time_elapsed: {time_elapsed}")
                messages_to_backend.send(app_state_manager.app_state.dict())
                if messages_from_backend.poll():
                    message = messages_from_backend.recv()
                    frontend_logger.info(f"frontend_main received message from backend: {message}")

            main_window = SkellyCamMainWindow()
            main_window.show()
            error_code = app.exec()
            frontend_logger.info(f"Exiting with code: {error_code}")

            exit_event.set()
        except Exception as e:
            frontend_logger.error(f"An error occurred: {e}")
            frontend_logger.exception(e)
            messages_to_backend.send({"type": "error",
                                      "message": str(e),
                                      "data": {}})
    frontend_logger.info(f"Exiting frontend_main")
    sys.exit(error_code)
