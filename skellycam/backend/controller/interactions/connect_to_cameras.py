import traceback
from typing import Dict

from pydantic import BaseModel

from skellycam.backend.controller import controller
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.system.environment.get_logger import logger


class ConnectToCamerasRequest(BaseModel):
    camera_configs: Dict[CameraId, CameraConfig]

class ConnectToCamerasResponse(BaseModel):
    success: bool
    metadata: Dict[str, str]

def connect_to_cameras(request: ConnectToCamerasRequest) -> ConnectToCamerasResponse:
        try:
            controller.camera_group_manager.start(camera_configs=request.camera_configs)
            return ConnectToCamerasResponse(success=True)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ConnectToCamerasResponse(success=False,
                                            metadata={"error": str(e),
                                                      "traceback": str(traceback.format_exc())})


