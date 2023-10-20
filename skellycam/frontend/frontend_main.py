import multiprocessing.connection

from PySide6.QtCore import QTimer

from skellycam import logger
from skellycam.backend.controller.interactions.base_models import BaseInteraction, BaseResponse
from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import MainWindow
from skellycam.frontend.manager.frontend_manager import FrontendManager


def frontend_main(messages_from_frontend: multiprocessing.Queue,
                  messages_from_backend: multiprocessing.Queue,
                  frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection,
                  exit_event: multiprocessing.Event,
                  reboot_event: multiprocessing.Event) -> int:
    def check_for_backend_messages():
        if not messages_from_backend.empty():
            response: BaseResponse = messages_from_backend.get()
            logger.info(f"frontend_main received message from backend: {response}")
            if not response.success:
                logger.error(f"Backend sent error message: {response}!")
            frontend_manager.handle_backend_response(response)

    def interact_with_backend(interaction: BaseInteraction) -> None:
        logger.debug(f"Sending interaction to backend: {interaction}")
        messages_from_frontend.put(interaction)

    app = create_or_recreate_qt_application()
    main_window = MainWindow(exit_event=exit_event, reboot_event=reboot_event)
    main_window.interact_with_backend.connect(lambda interaction: interact_with_backend(interaction))
    main_window.show()

    frontend_manager = FrontendManager(main_window=main_window,
                                       frontend_frame_pipe_receiver=frontend_frame_pipe_receiver)

    logger.info(f"Frontend listener loop starting...")
    update_timer = QTimer()
    update_timer.start(500)
    update_timer.timeout.connect(lambda: check_for_backend_messages())

    try:
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

    if not exit_event.is_set():
        logger.info(f"SETTING EXIT EVENT!")
        exit_event.set()
    logger.info(f"Exiting frontend_main")

    return exit_code
