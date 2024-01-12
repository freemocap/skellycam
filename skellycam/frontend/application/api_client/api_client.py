import asyncio
from typing import Dict

import httpx
from PySide6.QtCore import QObject, Signal
from pydantic import ValidationError

from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    CamerasDetectedResponse,
)
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.system.environment.get_logger import logger


class FrontendApiClient(QObject):
    detected_cameras = Signal(Dict[CameraId, CameraConfig])

    def __init__(self, api_base_url: str):
        super().__init__()
        self.client = httpx.AsyncClient(base_url=api_base_url)

    async def hello(self):
        return await self.client.get("hello")

    async def detect_cameras(self):
        logger.debug("Sending request to the frontend API `detect` endpoint")
        response = await self.client.get("detect")
        try:
            cameras_detected_response = CamerasDetectedResponse.parse_obj(
                response.json()
            )
            return cameras_detected_response
        except ValidationError as e:
            logger.error(f"Failed to parse response: {e}")
            return None


if __name__ == "__main__":
    from skellycam.api.run_server import run_backend
    from pprint import pprint

    backend_process_out, api_location_out = run_backend()
    print(f"Backend server is running on: {api_location_out}")
    client = FrontendApiClient(api_base_url=api_location_out)
    hello_response = asyncio.run(client.hello())
    pprint(hello_response.json())
    logger.info(f"Done!")
