import multiprocessing
from typing import Dict, Optional

from pydantic import BaseModel

from skellycam import logger
from skellycam.backend.controller.interactions.base_models import BaseInteraction, BaseResponse, \
    ErrorResponse
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.managers.video_recorder_manager import VideoRecorderManager
from skellycam.models.cameras.camera_device_info import CameraDeviceInfo

CONTROLLER = None


def get_or_create_controller() -> 'Controller':
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class Controller(BaseModel):
    camera_group_manager: Optional[CameraGroupManager]
    video_recorder_manager: Optional[VideoRecorderManager]
    available_cameras: Optional[Dict[str, CameraDeviceInfo]]
    frontend_frame_queue: Optional[multiprocessing.Queue]

    def handle_interaction(self, interaction: BaseInteraction) -> BaseResponse:
        logger.debug(f"Controller handling interaction: {interaction}")
        try:
            response = interaction.execute_command(controller=self)
            return response
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ErrorResponse.from_exception(exception=e)
