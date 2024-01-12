from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.application.api_client.get_or_create_api_client import (
    create_api_client,
)
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow


def run_frontend(api_url):
    logger.info(f"Starting frontend/client process...")

    create_api_client(api_url)

    qt_app = create_or_recreate_qt_application()

    main_window = SkellyCamMainWindow()
    exit_code = 0
    try:
        main_window.show()
        exit_code = qt_app.exec()
    except Exception as e:
        logger.error(e)
        logger.exception(e)
        exit_code = 1
    finally:
        main_window.close()
        return exit_code
