import logging
import time

from skellycam.api.routes.http.cameras.connect import ConnectCamerasResponse
from skellycam.api.routes.http.cameras.detect import DetectCamerasResponse
from skellycam.api.run_server import APP_URL
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.gui.client.http_client import HTTPClient
from skellycam.gui.client.websocket_client import WebSocketClient

logger = logging.getLogger(__name__)


class FastAPIClient:
    def __init__(self, base_url: str = APP_URL):
        self.http_client = HTTPClient(base_url)
        self.ws_client = WebSocketClient(base_url)


    def connect_to_cameras(self) -> ConnectCamerasResponse:
        logger.api("Calling `cameras/connect` endpoint")
        self.ws_client.connect()
        future_response = self.http_client.get("/cameras/connect")
        response = future_response.result()
        return ConnectCamerasResponse(**response.json())

    def detect_cameras(self) -> DetectCamerasResponse:
        logger.api("Calling `cameras/detect` endpoint")
        future_response = self.http_client.get("/cameras/detect")
        response = future_response.result()
        return DetectCamerasResponse(**response.json())

    def close_cameras(self):
        logger.api("Calling `cameras/close` endpoint")
        self.ws_client.close()
        future_response = self.http_client.get("/cameras/close")
        response = future_response.result()
        return response.json()

    def shutdown_server(self) -> None:
        logger.api("Calling `/app/shutdown` endpoint")

        self.close_cameras()
        time.sleep(1)
        self.http_client.get("/app/shutdown")
        self.http_client.close()
        self.ws_client.close()

    def start_recording(self):
        logger.api("Calling `/cameras/record/start` endpoint")
        self.http_client.get("/cameras/record/start")

    def stop_recording(self):
        logger.api("Calling `/cameras/record/stop` endpoint")
        self.http_client.get("/cameras/record/stop")

    def apply_settings_to_cameras(self, camera_configs: CameraConfigs):
        logger.api("Calling `/cameras/connect/apply` endpoint")
        self.http_client.post(endpoint="/cameras/connect/apply",
                              data=camera_configs)
