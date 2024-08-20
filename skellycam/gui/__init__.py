from skellycam.api.client.fastapi_client import FastAPIClient
from skellycam.api.server.run_server import get_server_manager

FASTAPI_CLIENT = None


def get_client() -> FastAPIClient:
    global FASTAPI_CLIENT
    if FASTAPI_CLIENT is None:
        FASTAPI_CLIENT = FastAPIClient()
    return FASTAPI_CLIENT


def shutdown_client_server() -> None:
    if get_server_manager().is_running:
        get_client().shutdown_server()
