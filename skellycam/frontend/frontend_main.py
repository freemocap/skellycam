import multiprocessing.connection
import sys

from PySide6.QtCore import QTimer

from skellycam import logger
from skellycam.data_models.request_response import Request
from skellycam.frontend.application import app_state_manager, create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.skelly_cam_main_window import MainWindow


def frontend_main(messages_from_backend: multiprocessing.connection.Connection,
                  messages_to_backend: multiprocessing.connection.Connection,
                  exit_event: multiprocessing.Event,
                  reboot_event: multiprocessing.Event):
    error_code = 0
    while not exit_event.is_set():
        logger.success(f"Frontend main started!")
        app = create_or_recreate_qt_application()
        main_window = None
        try:
            timer = QTimer()
            timer.start(500)
            logger.info(f"Frontend listening for messages from backend...")
            timer.timeout.connect(lambda: listen_for_backend_requests())  # Let the interpreter run each 500 ms.

            def listen_for_backend_requests():
                # logger.trace(f"Checking for messages from backend...")
                if exit_event.is_set() or reboot_event.is_set():
                    logger.info(f"Exit or reboot event set, quitting app...")
                    app.quit()

                if messages_from_backend.poll():
                    message = messages_from_backend.recv()
                    logger.info(f"frontend_main received message from backend: {message}")

            def update_backend(request: Request):
                logger.debug(f"Updating backend with request: {request}")
                app_state_manager.update(data=request.data)
                messages_to_backend.send(request.dict())

            main_window = MainWindow(exit_event=exit_event,
                                     reboot_event=reboot_event, )
            main_window.updated.connect(lambda: update_backend)
            main_window.show()
            error_code = app.exec()

            logger.info(f"Exiting with code: {error_code}")
            exit_event.set()

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
        finally:
            app.quit()
            if main_window:
                main_window.close()

        logger.info(f"Exiting frontend_main")
        sys.exit(error_code)
