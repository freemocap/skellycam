from typing import Optional

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.api_client import ApiClient

API_CLIENT: Optional[ApiClient] = None


def create_api_client(hostname: str, port: int) -> ApiClient:
    logger.debug(f"Creating api client for host: {hostname}, port: {port}")
    global API_CLIENT
    if API_CLIENT is None:
        API_CLIENT = ApiClient(hostname=hostname, port=port)
    return API_CLIENT
