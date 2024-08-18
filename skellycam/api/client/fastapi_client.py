import logging
import time

from skellycam.api.client.http_client import HTTPClient
from skellycam.api.client.websocket_client import WebSocketClient
from skellycam.api.server.routes.http.cameras.connect import ConnectCamerasResponse
from skellycam.api.server.routes.http.cameras.detect import DetectCamerasResponse
from skellycam.api.server.server_main import APP_URL, get_server_manager

logger = logging.getLogger(__name__)



class FastAPIClient:
    def __init__(self, base_url: str = APP_URL):
        self.http_client = HTTPClient(base_url)
        self.ws_client = WebSocketClient(base_url)

    def connect_to_cameras(self) -> ConnectCamerasResponse:
        logger.info("Calling /connect endpoint")
        future_response = self.http_client.get("/cameras/connect")
        response = future_response.result()
        return ConnectCamerasResponse(**response.json())

    def detect_cameras(self) -> DetectCamerasResponse:
        logger.info("Calling /detect endpoint")
        future_response = self.http_client.get("/cameras/detect")
        response = future_response.result()
        return DetectCamerasResponse(**response.json())

    def close_cameras(self):
        logger.info("Calling /close endpoint")
        future_response = self.http_client.get("/cameras/close")
        response = future_response.result()
        return response.json()

    def shutdown_server(self) -> None:
        logger.info("Shutting down server")

        self.close_cameras()
        time.sleep(1)
        self.http_client.get("/app/shutdown")
        self.http_client.close()
        self.ws_client.close()


FASTAPI_CLIENT = None


def get_client() -> FastAPIClient:
    global FASTAPI_CLIENT
    if FASTAPI_CLIENT is None:
        FASTAPI_CLIENT = FastAPIClient()
    return FASTAPI_CLIENT


def shutdown_client_server() -> None:
    if get_server_manager().is_running:
        get_client().shutdown_server()

# Example usage
if __name__ == "__main__":
    client = FastAPIClient()

    try:
        # Example GET request
        future_response = client.http_client.get("/hello")
        response = future_response.result()
        print(response.json())

        # Start WebSocket connection
        client.ws_client.start_websocket()
        time.sleep(5)
    finally:
        client.close()