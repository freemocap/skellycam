import logging

from skellycam.api.server_constants import APP_URL
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.gui.client.http_client import HTTPClient
from skellycam.gui.client.websocket_client import WebSocketClient

logger = logging.getLogger(__name__)


class FastAPIClient:
    def __init__(self, base_url: str = APP_URL):
        self.http_client = HTTPClient(base_url)
        self.ws_client = WebSocketClient(base_url)

    def connect_websocket(self):
        logger.api("Client sending request to connect to WebSocket")
        self.ws_client.connect_websocket()

    def connect_to_cameras(self):
        logger.api("Calling `cameras/connect` endpoint")
        self.http_client.get("/cameras/connect")

    def detect_cameras(self):
        logger.api("Calling `cameras/detect` endpoint")
        self.http_client.get("/cameras/detect")

    def close_cameras(self):
        logger.api("Calling `cameras/close` endpoint")
        self.ws_client.close()
        self.http_client.get("/cameras/close")

    def shutdown_server(self) -> None:
        logger.api("Calling `/app/shutdown` endpoint")
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
        if not camera_configs:
            raise ValueError("CameraConfigs are `None`")
        data = {camera_id: config.model_dump() for camera_id, config in camera_configs.items()}
        self.http_client.post(endpoint="/cameras/connect/apply",
                              data=data)
