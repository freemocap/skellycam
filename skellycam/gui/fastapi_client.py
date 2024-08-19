import logging
import time

from skellycam.api.client.http_client import HTTPClient
from skellycam.api.client.websocket_client import WebSocketClient
from skellycam.api.server.routes.http.cameras.connect import ConnectCamerasResponse
from skellycam.api.server.routes.http.cameras.detect import DetectCamerasResponse
from skellycam.api.server.run_server import APP_URL

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
