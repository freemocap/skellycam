import asyncio
from typing import Dict, Optional

import httpx
import websocket
from PySide6.QtCore import QObject, Signal, Slot
from pydantic import ValidationError
from websockets import WebSocketClientProtocol

from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.controller.interactions.connect_to_cameras import (
    CamerasConnectedResponse,
)
from skellycam.backend.models.cameras import camera_config
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.system.environment.get_logger import logger


class FrontendApiClient(QObject):
    detected_cameras = Signal(Dict[CameraId, CameraConfig])

    def __init__(self, hostname: str, port: int) -> None:
        super().__init__()

        self.api_base_url = f"http://{hostname}:{port}"
        self.client = httpx.Client(base_url=self.api_base_url)

        self.websocket_url = f"ws://{hostname}:{port}/websocket"
        self.websocket = self.get_websocket()

    def hello(self):
        return self.client.get("hello")

    def detect_cameras(self):
        logger.debug("Sending request to the frontend API `detect` endpoint")
        response = self.client.get("detect")
        try:
            cameras_detected_response = CamerasDetectedResponse.parse_obj(
                response.json()
            )
            return cameras_detected_response
        except ValidationError as e:
            logger.error(f"Failed to parse response: {e}")
            return None

    def connect_to_cameras(self, camera_configs: CameraConfigs):
        logger.debug("Sending request to the frontend API `connect` endpoint")
        request_body = {
            id: camera_config.json() for id, camera_config in camera_configs.items()
        }
        response = self.client.post("connect", json=request_body)
        try:
            cameras_detected_response = CamerasConnectedResponse.parse_obj(
                response.json()
            )
            return cameras_detected_response
        except ValidationError as e:
            logger.error(f"Failed to parse response: {e}")
            return None

    def get_websocket(self) -> Optional[websocket.WebSocket]:
        logger.debug(f"Establishing WebSocket connection to: {self.websocket_url}")
        try:
            self.websocket = websocket.create_connection(self.websocket_url)
            if self.websocket is None:
                Exception("WebSocket failed to connect")
        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection: {e}")
            return None
        return self.websocket


if __name__ == "__main__":
    from skellycam.api.run_server import run_backend
    from pprint import pprint

    backend_process_out, api_location_out = run_backend()
    print(f"Backend server is running on: {api_location_out}")
    client = FrontendApiClient(api_base_url=api_location_out)
    hello_response = asyncio.run(client.hello())
    pprint(hello_response.json())
    print(f"Done!")
