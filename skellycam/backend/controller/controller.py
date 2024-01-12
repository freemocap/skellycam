import traceback
from typing import Dict

from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras, CamerasDetectedResponse
from skellycam.backend.controller.interactions.connect_to_cameras import ConnectToCamerasResponse
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.system.environment.get_logger import logger

CONTROLLER = None
def get_or_create_controller() -> 'Controller':
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class Controller:

    def __init__(self):
        self.available_cameras = None
        self.camera_group_manager = CameraGroupManager()



    def detect_available_cameras(self) -> CamerasDetectedResponse:
        cameras_detected_response =detect_available_cameras()
        self.available_cameras = cameras_detected_response.available_cameras
        if not self.available_cameras:
            logger.warning("No cameras detected!")
        return cameras_detected_response

    def connect_to_cameras(self, camera_configs: Dict[CameraId, CameraConfig]):

        if not self.available_cameras:
            logger.error("No cameras available")
            Exception("No cameras available")
        if not camera_configs:
            logger.error("Must provide at least one camera config")
            Exception("Must provide at least one camera config")

        try:
            self.camera_group_manager.start(camera_configs=camera_configs)
            return ConnectToCamerasResponse(success=True)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ConnectToCamerasResponse(success=False,
                                            metadata={"error": str(e),
                                                      "traceback": str(traceback.format_exc())})

