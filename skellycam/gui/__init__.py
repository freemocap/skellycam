from skellycam.api.server_manager import get_server_manager
from skellycam.gui.client.fastapi_client import FastAPIClient

FASTAPI_CLIENT = None


def get_client() -> FastAPIClient:
    global FASTAPI_CLIENT
    if FASTAPI_CLIENT is None:
        FASTAPI_CLIENT = FastAPIClient()
    return FASTAPI_CLIENT


def shutdown_client_server() -> None:
    if get_server_manager().is_running:
        get_client().shutdown_server()
