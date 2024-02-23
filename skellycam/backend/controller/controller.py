import logging
import traceback
from typing import Dict, Optional

from skellycam.backend.api_server.requests_responses.connect_to_cameras_request_response import (
    CamerasConnectedResponse,
)
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import (
    CameraGroupManager,
)
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import (
    detect_available_cameras,
    CamerasDetectedResponse,
    DetectedCameras,
)
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.camera_id import CameraId

logger = logging.getLogger(__name__)

CONTROLLER = None


def get_or_create_controller() -> "Controller":
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class Controller:
    def __init__(self):
        self.detected_cameras = None
        self.camera_group_manager: Optional[CameraGroupManager] = None

    def detect_available_cameras(self) -> CamerasDetectedResponse:
        cameras_detected_response = detect_available_cameras()
        self.detected_cameras: DetectedCameras = (
            cameras_detected_response.detected_cameras
        )
        if not self.detected_cameras:
            logger.warning("No cameras detected!")
        return cameras_detected_response

    def connect_to_cameras(self, camera_configs: Dict[CameraId, CameraConfig]):
        for camera_id in camera_configs.keys():
            if camera_id not in self.detected_cameras.keys():
                logger.warning(
                    f"Camera {camera_id} was not found in list of previously detected cameras "
                    f"{list(self.detected_cameras.keys())} - (We'll still try to contect to it though)"
                )

        if not camera_configs or len(camera_configs) == 0:
            logger.error("Must provide at least one camera config")
            Exception("Must provide at least one camera config")

        try:
            self.camera_group_manager = CameraGroupManager(
                camera_configs=camera_configs
            )
            self.camera_group_manager.start()
            # self.camera_group_manager.join()
            return CamerasConnectedResponse(success=True)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return CamerasConnectedResponse(
                success=False,
                metadata={"error": str(e), "traceback": str(traceback.format_exc())},
            )

    def close_cameras(self):
        if self.camera_group_manager is not None:
            self.camera_group_manager.close()
            self.camera_group_manager = None
            return True
        return False

    def start_recording(self, recording_folder_path: str):
        if self.camera_group_manager is not None:
            self.camera_group_manager.start_recording(recording_folder_path)
            return True
        return False

    def update_camera_configs(self, camera_configs: CameraConfigs):
        logger.info("Updating camera configs...")
        if self.camera_group_manager is not None:
            self.camera_group_manager.update_camera_configs(camera_configs)
            return {"success": True}
        return {"success": False, "error": "No camera group manager found"}

    def stop_recording(self):
        logger.info("Stopping recording...")
        if self.camera_group_manager is not None:
            self.camera_group_manager.stop_recording()
            return True
