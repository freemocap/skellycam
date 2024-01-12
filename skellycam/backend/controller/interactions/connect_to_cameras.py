import traceback
from typing import Dict

from pydantic import BaseModel

from skellycam.backend.controller import controller
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import (
    CameraGroupManager,
)
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.system.environment.get_logger import logger


class ConnectToCamerasRequest(BaseModel):
    camera_configs: Dict[CameraId, CameraConfig]


class CamerasConnectedResponse(BaseModel):
    # TODO - Return the actual settings that the cameras are running, in case they quietly reject any of the requested camera settings
    success: bool
    metadata: Dict[str, str]


def connect_to_cameras(
    camera_group_manager: CameraGroupManager, camera_configs: CameraConfigs
) -> CamerasConnectedResponse:
    try:
        camera_group_manager.start(camera_configs=camera_configs)
        return CamerasConnectedResponse(success=True)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.exception(e)
        return CamerasConnectedResponse(
            success=False,
            metadata={"error": str(e), "traceback": str(traceback.format_exc())},
        )
