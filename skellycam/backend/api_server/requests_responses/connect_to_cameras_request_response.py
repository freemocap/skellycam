import logging
from typing import Dict, Optional

from pydantic import BaseModel

from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_configs import (
    DEFAULT_CAMERA_CONFIGS,
)
from skellycam.backend.models.cameras.camera_id import CameraId

logger = logging.getLogger(__name__)


class ConnectToCamerasRequest(BaseModel):
    camera_configs: Dict[CameraId, CameraConfig]

    @classmethod
    def default(cls) -> "ConnectToCamerasRequest":
        return cls(camera_configs=DEFAULT_CAMERA_CONFIGS)


class CamerasConnectedResponse(BaseModel):
    # TODO - Return the actual settings that the cameras are running, in case they quietly reject any of the requested camera settings
    success: bool
    metadata: Optional[Dict[str, str]]