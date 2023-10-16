from typing import Dict, Optional

from skellycam import logger
from skellycam.backend.controller.commands.requests_commands import BaseInteraction, BaseResponse, \
    ErrorResponse
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.managers.video_recorder_manager import VideoRecorderManager
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo

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

    def handle_interaction(self, interaction: BaseInteraction) -> BaseResponse:
        logger.debug(f"Controller handling interaction: {interaction}")
        try:
            response = interaction.execute_command(controller=self)
            logger.debug(f"Controller handled interaction: {interaction}")
            return response
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ErrorResponse.from_exception(exception=e)
