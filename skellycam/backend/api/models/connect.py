from typing import Dict, Optional

from pydantic import BaseModel

from skellycam.backend.core.cameras.config.camera_config import CameraConfig, DEFAULT_CAMERA_CONFIGS
from skellycam.backend.core.device_detection.camera_id import CameraId


class ConnectToCamerasRequest(BaseModel):
    camera_configs: Dict[CameraId, CameraConfig]

    @classmethod
    def default(cls) -> "ConnectToCamerasRequest":
        return cls(camera_configs=DEFAULT_CAMERA_CONFIGS)


class CamerasConnectedResponse(BaseModel):
    # TODO - Return the actual settings that the cameras are running, in case they quietly reject any of the requested camera settings
    success: bool
    metadata: Optional[Dict[str, str]]