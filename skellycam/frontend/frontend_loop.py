import multiprocessing.connection
import pprint
import sys
import warnings

from PySide6.QtCore import QTimer

from skellycam import logger
from skellycam.data_models.request_response_update import UpdateModel
from skellycam.frontend.application import app_state_manager, create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import MainWindow


def frontend_loop(messages_from_frontend: multiprocessing.Queue,
                  messages_from_backend: multiprocessing.Queue,
                  exit_event: multiprocessing.Event,
                  reboot_event: multiprocessing.Event):
    error_code = 0
    while not exit_event.is_set():
        logger.success(f"Frontend main started!")
        app = create_or_recreate_qt_application()
        main_window = None
        try:

            def listen_for_backend_requests():
                # logger.trace(f"Checking for messages from backend...")
                if not messages_from_backend.empty():
                    message = messages_from_backend.get()
                    logger.info(
                        f"frontend_main received message from backend: \n {pprint.pformat(message)} \n- queue size: {messages_from_backend.qsize()}")
                    if not message.type == "success":
                        logger.error(f"Backend sent error message: {message.message}")
                        warnings.warn(f"Backend sent error message: {message.message}")

            def update_backend(update: UpdateModel):
                logger.debug(f"Updating backend with:\n {update}")
                app_state_manager.update(update=update)
                messages_from_frontend.put(update.dict())

            logger.info(f"Frontend lister loop starting...")
            timer = QTimer()
            timer.start(500)
            timer.timeout.connect(lambda: listen_for_backend_requests())  # Let the interpreter run each 500 ms.

            main_window = MainWindow(exit_event=exit_event,
                                     reboot_event=reboot_event, )
            main_window.updated.connect(lambda update: update_backend(update))
            main_window.show()
            error_code = app.exec()

            logger.info(f"Exiting with code: {error_code}")
            if not exit_event.is_set():
                logger.info(f"SETTING EXIT EVENT!")
                exit_event.set()
                break

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            raise e

        finally:
            if not exit_event.is_set():
                logger.info(f"SETTING EXIT EVENT!")
                exit_event.set()
            app.quit()
            if main_window:
                main_window.close()

        logger.info(f"Exiting frontend_main")
        sys.exit(error_code)
