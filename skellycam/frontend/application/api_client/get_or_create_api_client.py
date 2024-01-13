from typing import Optional

from skellycam.api.frontend_client.api_client import FrontendApiClient
from skellycam.backend.system.environment.get_logger import logger

API_CLIENT: Optional[FrontendApiClient] = None


def create_api_client(api_url: str) -> FrontendApiClient:
    logger.debug(f"Creating api client for url:  {api_url}")
    global API_CLIENT
    if API_CLIENT is None:
        API_CLIENT = FrontendApiClient(api_base_url=api_url)
    return API_CLIENT
