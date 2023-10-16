import traceback
from typing import Dict, Optional

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.backend.controller.managers.video_recorder_manager import VideoRecorderManager
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.request_response_update import Response, CamerasDetected, DetectAvailableCameras, \
    ConnectToCameras, BaseMessage

CONTROLLER = None


def get_or_create_controller():
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class Controller:
    camera_group_manager: Optional[CameraGroupManager]
    video_recorder_manager: VideoRecorderManager = None
    available_cameras: Dict[str, CameraDeviceInfo] = None

    def handle_message(self, message: BaseMessage) -> Response:
        logger.debug(f"Controller received message:\n {message}")
        response = None
        try:
            match message.__class__:
                case DetectAvailableCameras.__class__:
                    self.available_cameras = detect_available_cameras()
                    logger.debug(f"Detected available self.available_cameras: "
                                 f"{[camera.description for camera in self.available_cameras.values()]}")
                    response = CamerasDetected(success=True,
                                               available_cameras = self.available_cameras)

                case ConnectToCameras.__class__:
                    self.camera_group_manager = CameraGroupManager(camera_configs=message.data["camera_configs"])
                    self.camera_group_manager.start()


        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            response = Response(success=False,
                                data={"error": str(e),
                                      "traceback": traceback.format_exc()})
        finally:
            if response is None:
                response = Response(sucess=False,
                                    data={"message": "No response was generated!"})
            logger.debug(f"Controller generated response: response.success = {response.success}")

        return response
