import logging

logger = logging.getLogger(__name__)
from skellycam.frontend.api_client.api_client import ApiClient
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient

from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow


def run_frontend(
    hostname: str,
    port: int,
) -> int:
    logger.info(f"Starting frontend/client process...")
    exit_code = 0
    skellycam_qt_app = None
    try:
        skellycam_qt_app = create_or_recreate_qt_application(hostname, port)
        exit_code = skellycam_qt_app.exec()
    except Exception as e:
        logger.error(e)
        logger.exception(e)
        exit_code = 1
    finally:
        if skellycam_qt_app is not None:
            skellycam_qt_app.quit()
    return exit_code
