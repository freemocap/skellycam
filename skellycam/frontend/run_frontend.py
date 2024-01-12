import multiprocessing.connection

from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow
from skellycam.backend.system.environment.get_logger import logger


def run_frontend(api_url):
    logger.info(f"Starting frontend/client process...")
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
