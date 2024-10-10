from skellycam.gui.client.fastapi_client import FastAPIClient

FASTAPI_CLIENT = None


def get_client() -> FastAPIClient:
    global FASTAPI_CLIENT
    if FASTAPI_CLIENT is None:
        FASTAPI_CLIENT = FastAPIClient()
    return FASTAPI_CLIENT
