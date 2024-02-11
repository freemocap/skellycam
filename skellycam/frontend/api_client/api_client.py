import httpx
from PySide6.QtCore import QObject, Signal
from httpx import Timeout
from pydantic import ValidationError

from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
    DetectedCameras,
)
from skellycam.backend.controller.interactions.connect_to_cameras import (
    CamerasConnectedResponse,
    ConnectToCamerasRequest,
)
from skellycam.backend.models.cameras.camera_configs import (
    CameraConfigs,
    DEFAULT_CAMERA_CONFIGS,
)
from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketManager


class ApiClient(QObject):
    detected_cameras = Signal(CamerasDetectedResponse)
    cameras_connected = Signal()

    def __init__(self, hostname: str, port: int, timeout: float = 10) -> None:
        super().__init__()

        self.api_base_url = f"http://{hostname}:{port}"
        self.client = httpx.Client(base_url=self.api_base_url, timeout=timeout)

        self.websocket_url = f"ws://{hostname}:{port}/websocket"
        self.websocket_connection = FrontendWebsocketManager(url=self.websocket_url)

    def hello(self):
        return self.client.get("hello")

    def detect_available_cameras(self):
        logger.debug("Sending request to the frontend API `detect` endpoint")
        response = self.client.get("detect")
        try:
            cameras_detected_response = CamerasDetectedResponse.parse_obj(
                response.json()
            )
            self.detected_cameras.emit(cameras_detected_response)

        except ValidationError as e:
            logger.error(f"Failed to parse response: {e}")
            return None

    def connect_to_cameras(self, camera_configs: CameraConfigs, timeout: float = 60):
        logger.debug("Sending request to the frontend API `connect` endpoint")
        request = ConnectToCamerasRequest(camera_configs=camera_configs).dict()
        custom_timeout = Timeout(timeout)
        response = self.client.post("connect", json=request, timeout=custom_timeout)
        try:
            cameras_detected_response = CamerasConnectedResponse.parse_obj(
                response.json()
            )
            if cameras_detected_response.success:
                self.cameras_connected.emit()
            return cameras_detected_response
        except ValidationError as e:
            logger.error(f"Failed to parse response: {e}")
            return None

    # def get_latest_frames(self):
    #     logger.debug("Sending request for the get latest frames endpoint")
    #     response = self.client.get("cameras/latest_frames", follow_redirects=True)
    #
    #     if response.status_code != 200:
    #         logger.error(
    #             f"Failed to fetch latest frames, status code: {response.status_code}"
    #         )
    #         return None
    #
    #     try:
    #         byte_chunks = response.iter_bytes()
    #         content = b"".join(byte_chunks)
    #
    #         multi_frame_payload = MultiFramePayload.from_bytes(content)
    #         return multi_frame_payload
    #     except ValidationError as e:
    #         logger.error(f"Failed to parse response: {e}")
    #         return None
    #     except Exception as e:
    #         logger.error(f"An unexpected error occurred: {e}")
    #         return None


def check_frontend_camera_connection():
    from skellycam.api.run_server import run_backend
    from pprint import pprint

    backend_process_out, hostname, port = run_backend()
    print(f"Backend server is running on: https://{hostname}:{port}")
    client = ApiClient(hostname, port)
    hello_response = client.hello()
    pprint(hello_response.json())
    c = DEFAULT_CAMERA_CONFIGS
    print(client.connect_to_cameras(c))

    payload = client.get_latest_frames()
    pprint(payload)


if __name__ == "__main__":
    check_frontend_camera_connection()
    print(f"Done!")
