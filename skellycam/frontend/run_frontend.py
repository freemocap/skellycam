import multiprocessing

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient
from skellycam.frontend.api_client.get_or_create_api_client import create_api_client


from skellycam.frontend.application import create_or_recreate_qt_application
from skellycam.frontend.gui.main_window.main_window import SkellyCamMainWindow


def run_frontend(
    hostname: str,
    port: int,
) -> int:
    logger.info(f"Starting frontend/client process...")

    backend_http_url = f"http://{hostname}:{port}"
    api_client = create_api_client(backend_http_url)

    backend_websocket_url = f"ws://{hostname}:{port}/websocket"
    websocket_client = FrontendWebsocketClient(backend_websocket_url)
    websocket_client.connect_to_server()
    websocket_client.send_ping()

    main_window = SkellyCamMainWindow(api_client, websocket_client)

    qt_app = create_or_recreate_qt_application()

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
