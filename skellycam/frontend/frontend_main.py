import multiprocessing.connection
import warnings

from PySide6.QtCore import QTimer

from skellycam import logger
from skellycam.data_models.request_response_update import UpdateModel, MessageType
from skellycam.frontend.application import app_state_manager, create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import MainWindow


def frontend_main(messages_from_frontend: multiprocessing.Queue,
                  messages_from_backend: multiprocessing.Queue,
                  exit_event: multiprocessing.Event,
                  reboot_event: multiprocessing.Event) -> int:
    exit_code = frontend_loop(messages_from_frontend=messages_from_frontend,
                              messages_from_backend=messages_from_backend,
                              exit_event=exit_event,
                              reboot_event=reboot_event)

    if not exit_event.is_set():
        logger.info(f"SETTING EXIT EVENT!")
        exit_event.set()
    logger.info(f"Exiting frontend_main")
    return exit_code


def frontend_loop(messages_from_frontend: multiprocessing.Queue,
                  messages_from_backend: multiprocessing.Queue,
                  exit_event: multiprocessing.Event,
                  reboot_event: multiprocessing.Event):
    exit_code = 0
    main_window = None
    app = None
    try:
        while not exit_event.is_set():
            logger.success(f"Frontend main started!")
            app = create_or_recreate_qt_application()

            def check_for_backend_messages():
                # logger.trace(f"Checking for messages from backend...")
                if not messages_from_backend.empty():
                    response = messages_from_backend.get()
                    logger.info(f"frontend_main received message from backend: \n {response.message_type}")
                    if not response.success:
                        logger.error(f"Backend sent error message: {response.data['error']}!")
                    main_window.update_view(response)

            def update_backend(update: UpdateModel):
                logger.debug(f"Updating backend with:\n {update}")
                app_state_manager.update(update=update)
                messages_from_frontend.put(update.dict())

            logger.info(f"Frontend lister loop starting...")
            update_timer = QTimer()
            update_timer.start(500)
            update_timer.timeout.connect(lambda: check_for_backend_messages())  # Let the interpreter run each 500 ms.


            main_window = MainWindow(exit_event=exit_event,
                                     reboot_event=reboot_event, )
            main_window.updated.connect(lambda update: update_backend(update))
            main_window.show()
            exit_code = app.exec()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        raise e
    finally:
        if main_window is not None:
            main_window.close()
        if app is not None:
            app.quit()

    return exit_code
