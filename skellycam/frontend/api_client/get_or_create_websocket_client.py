from typing import Optional

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.api_client import ApiClient
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient

FRONTEND_WEBSOCKET_CLIENT: Optional[ApiClient] = None


def create_websocket_client(url: str) -> FrontendWebsocketClient:
    logger.debug(f"Creating api client for url: {url}")
    global FRONTEND_WEBSOCKET_CLIENT
    if FRONTEND_WEBSOCKET_CLIENT is None:
        FRONTEND_WEBSOCKET_CLIENT = FrontendWebsocketClient(url)
    return FRONTEND_WEBSOCKET_CLIENT
