import multiprocessing

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.get_or_create_api_client import create_api_client

from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow


def run_frontend(
    hostname: str,
    port: int,
) -> int:
    logger.info(f"Starting frontend/client process...")

    api_client = create_api_client(hostname=hostname, port=port)

    qt_app = create_or_recreate_qt_application()

    main_window = SkellyCamMainWindow(api_client)
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
