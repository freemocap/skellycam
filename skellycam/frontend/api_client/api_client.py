import logging
import multiprocessing

import httpx
from PySide6.QtCore import QObject
from httpx import Timeout
from pydantic import ValidationError

from skellycam.backend.api.models.connect_to_cameras_request_response import (
    CamerasConnectedResponse,
    ConnectToCamerasRequest,
)
from skellycam.backend.core.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.models.cameras.camera_configs import (
    CameraConfigs,
    DEFAULT_CAMERA_CONFIGS,
)

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel("INFO")


class ApiClient(QObject):
    def __init__(self, url: str, timeout: float = 600) -> None:
        logger.info(f"Initializing API client with base URL: {url}")
        super().__init__()

        self.api_base_url = url
        self.client = httpx.Client(base_url=self.api_base_url, timeout=timeout)

    def hello(self):
        logger.debug("Sending request to the frontend API `hello` endpoint")
        return self.client.get("hello")

    def detect_available_cameras(self):
        logger.debug("Sending request to the frontend API `detect` endpoint")
        response = self.client.get("detect")
        logger.debug(f"Response: {response}")
        try:
            cameras_detected_response = CamerasDetectedResponse.parse_obj(
                response.json()
            )
            logger.success(
                f"Detected cameras: {cameras_detected_response.detected_cameras.keys()}"
            )
            return cameras_detected_response

        except ValidationError as e:
            logger.error(f"Failed to parse response: {e}")
            return None

    def connect_to_cameras(self, camera_configs: CameraConfigs, timeout: float = 60):
        logger.debug("Sending request to the frontend API `connect` endpoint")
        request = ConnectToCamerasRequest(camera_configs=camera_configs).dict()
        custom_timeout = Timeout(timeout)
        response = self.client.post("connect", json=request, timeout=custom_timeout)
        logger.debug(f"Response: {response.json()}")
        try:
            cameras_detected_response = CamerasConnectedResponse.parse_obj(
                response.json()
            )
            if cameras_detected_response.success:
                logger.success("Connected to cameras!")
                return cameras_detected_response
            else:
                logger.error(
                    f"Failed to connect to cameras: {cameras_detected_response}"
                )
        except ValidationError as e:
            logger.error(f"Failed to parse CamerasConnectedResponse with error: '{e}'")

    def get_latest_frames(self):
        logger.trace("Sending request to the frontend API `latest_frame` endpoint")
        response = self.client.get("latest_frames")
        logger.trace(f"Response: {response}")
        return response

    def close_cameras(self):
        logger.info("Sending request to the frontend API `close` endpoint")
        response = self.client.get("close")
        logger.info(f"Response: {response}")
        return response

    def update_camera_configs(self, camera_configs: CameraConfigs):
        logger.info(
            "Sending request to the frontend API `update_camera_configs` endpoint"
        )
        configs_as_dict = {
            camera_id: camera_config.dict()
            for camera_id, camera_config in camera_configs.items()
        }
        response = self.client.post("update_camera_configs", json=configs_as_dict)
        logger.info(f"Response: {response}")
        return response

    def start_recording(self, recording_folder_path: str):
        logger.info("Sending request to the frontend API `start_recording` endpoint")
        response = self.client.post(
            "start_recording", json={"recording_folder_path": recording_folder_path}
        )
        logger.info(f"Response: {response}")
        return response

    def stop_recording(self):
        logger.info("Sending request to the frontend API `stop_recording` endpoint")
        response = self.client.get("stop_recording")
        logger.info(f"Response: {response}")
        return response


def check_frontend_camera_connection():
    from skellycam.backend.run_backend import run_backend
    from pprint import pprint

    ready_event = multiprocessing.Event()
    backend_process_out, hostname, port = run_backend(ready_event)
    print(f"Backend server is running on: https://{hostname}:{port}")
    client = ApiClient(hostname, port)
    hello_response = client.hello()
    pprint(hello_response.json())
    c = DEFAULT_CAMERA_CONFIGS
    print(client.connect_to_cameras(c))


if __name__ == "__main__":
    check_frontend_camera_connection()
    print(f"Done!")
