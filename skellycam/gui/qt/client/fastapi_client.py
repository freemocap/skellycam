import logging

from PySide6.QtWidgets import QWidget

from skellycam.api.server.server_constants import APP_URL
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.gui.qt.client.http_client import HTTPClient
from skellycam.gui.qt.client.websocket_client import WebSocketClient

logger = logging.getLogger(__name__)


class FastAPIClient(QWidget):
    def __init__(self, parent: QWidget, base_url: str = APP_URL):
        super().__init__(parent=parent)
        self._http_client = HTTPClient(base_url=base_url,
                                       parent=self)
        self._ws_client = WebSocketClient(base_url=base_url,
                                          parent=self)

    @property
    def http_client(self) -> HTTPClient:
        return self._http_client

    @property
    def websocket_client(self) -> WebSocketClient:
        return self._ws_client

    def connect_websocket(self):
        logger.gui("Client sending request to connect to WebSocket")
        self._ws_client.connect_websocket()

    def detect_cameras(self):
        logger.gui("Calling `cameras/detect` endpoint")
        self._http_client.get("/cameras/detect")

    def close_cameras(self):
        logger.gui("Calling `cameras/close` endpoint")
        self._http_client.get("/cameras/close")

    def shutdown_server(self) -> None:
        logger.gui("Calling `/app/shutdown` endpoint")
        self._http_client.get("/app/shutdown")
        self._http_client.close()
        self._ws_client.close()

    def start_recording(self):
        logger.gui("Calling `/cameras/record/start` endpoint")
        self._http_client.get("/cameras/record/start")

    def stop_recording(self):
        logger.gui("Calling `/cameras/record/stop` endpoint")
        self._http_client.get("/cameras/record/stop")

    def detect_and_connect_to_cameras(self):
        logger.gui("Calling `cameras/connect` endpoint")
        self._http_client.get("/cameras/connect/detect")

    def apply_settings_to_cameras(self, camera_configs: CameraConfigs):
        logger.gui("Calling `/cameras/connect/apply` endpoint")
        if not camera_configs:
            raise ValueError("CameraConfigs are `None`")
        data = {camera_id: config.model_dump() for camera_id, config in camera_configs.items()}
        self._http_client.post(endpoint="/cameras/connect/apply",
                               data=data)
