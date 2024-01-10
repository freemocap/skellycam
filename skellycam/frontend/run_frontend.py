import multiprocessing.connection

from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow
from skellycam.system.environment.get_logger import logger


def run_frontend():
    app = create_or_recreate_qt_application()
    main_window = SkellyCamMainWindow()
    exit_code = 0
    try:
        main_window.show()
        exit_code = app.exec()
    except Exception as e:
        logger.error(e)
        logger.exception(e)
        exit_code = 1
    finally:
        main_window.close()
        return exit_code





def frontend_main(messages_from_frontend: multiprocessing.Queue,
                  messages_from_backend: multiprocessing.Queue,
                  frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection,
                  exit_event: multiprocessing.Event,
                  reboot_event: multiprocessing.Event) -> int:
    app = create_or_recreate_qt_application()
    main_window = SkellyCamMainWindow(exit_event=exit_event,
                                      reboot_event=reboot_event,
                                      messages_from_frontend=messages_from_frontend,
                                      messages_from_backend=messages_from_backend,
                                      frontend_frame_pipe_receiver=frontend_frame_pipe_receiver,
                                      )
    main_window.show()

    try:
        exit_code = app.exec()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info(f"Closing main window and quitting app...")
        if main_window is not None:
            main_window.close()
        if app is not None:
            app.quit()

    if not exit_event.is_set():
        logger.info(f"SETTING EXIT EVENT!")
        exit_event.set()

    logger.info(f"Exiting frontend_main")

    return exit_code
