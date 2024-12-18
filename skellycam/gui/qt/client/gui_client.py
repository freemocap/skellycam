import logging

from PySide6.QtWidgets import QWidget

from skellycam.api.server.server_constants import APP_URL
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.recorders.start_recording_request import StartRecordingRequest
from skellycam.gui.qt.client.http_client import HTTPClient
from skellycam.gui.qt.client.websocket_client import WebSocketClient

logger = logging.getLogger(__name__)


class SkellycamFrontendClient(QWidget):
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
        logger.gui("Calling `/skellycam/cameras/detect` endpoint")
        self._http_client.get("/skellycam/cameras/detect")

    def close_cameras(self):
        logger.gui("Calling `/skellycam/cameras/close` endpoint")
        self._http_client.get("/skellycam/cameras/close")

    def shutdown_server(self) -> None:
        logger.gui("Calling `/skellycam/app/shutdown` endpoint")
        self._http_client.get("/skellycam/app/shutdown")
        self._http_client.close()
        self._ws_client.close()

    def start_recording(self, start_recording_request:StartRecordingRequest):
        logger.gui("Calling `/skellycam/cameras/record/start` endpoint")
        self._http_client.post(endpoint="/skellycam/cameras/record/start",
                               data=start_recording_request.model_dump())

    def stop_recording(self):
        logger.gui("Calling `/skellycam/cameras/record/stop` endpoint")
        self._http_client.get("/skellycam/cameras/record/stop")

    # def detect_and_connect_to_cameras(self):
    #     logger.gui("Calling `cameras/connect` endpoint")
    #
    #     self._http_client.get("/cameras/connect/detect")

    def cameras_connect_apply(self, camera_configs: CameraConfigs):
        logger.gui("Calling `/skellycam/cameras/connect/apply` endpoint")
        if not camera_configs:
            raise ValueError("CameraConfigs are `None`")
        data = {camera_id: config.model_dump() for camera_id, config in camera_configs.items()}
        self._http_client.post(endpoint="/skellycam/cameras/connect/apply",
                               data=data)

    def cameras_connect_detect(self):
        logger.gui("Calling `/skellycam/cameras/connect/detect` endpoint")
        self._http_client.get("/skellycam/cameras/connect/detect")
