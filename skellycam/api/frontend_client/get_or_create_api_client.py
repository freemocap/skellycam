from typing import Optional

from skellycam.api.frontend_client.api_client import FrontendApiClient
from skellycam.backend.system.environment.get_logger import logger

API_CLIENT: Optional[FrontendApiClient] = None


def create_api_client(hostname: str, port: int) -> FrontendApiClient:
    logger.debug(f"Creating api client for host: {hostname}, port: {port}")
    global API_CLIENT
    if API_CLIENT is None:
        API_CLIENT = FrontendApiClient(hostname=hostname, port=port)
    return API_CLIENT
