from typing import Optional

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.application.api_client import FrontendApiClient

API_CLIENT: Optional[FrontendApiClient] = None


def create_api_client(api_url: str) -> FrontendApiClient:
    logger.debug(f"Creating api client for url:  {api_url}")
    global API_CLIENT
    if API_CLIENT is None:
        API_CLIENT = FrontendApiClient(api_base_url=api_url)
    return API_CLIENT


def get_api_client() -> FrontendApiClient:
    global API_CLIENT
    if API_CLIENT is None:
        Exception("API Client has not been initialized yet!")
    return API_CLIENT
