from typing import Optional

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.api_client import ApiClient

API_CLIENT: Optional[ApiClient] = None


def create_api_client(url: str) -> ApiClient:
    logger.debug(f"Creating api client at url: {url}")
    global API_CLIENT
    if API_CLIENT is None:
        API_CLIENT = ApiClient(url)
    return API_CLIENT
