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


def get_or_create_controller(frontend_frame_queue:multiprocessing.Queue) -> 'Controller':
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller(frontend_frame_queue=frontend_frame_queue)
    return CONTROLLER


class Controller:

    def __init__(self, frontend_frame_queue: multiprocessing.Queue):
        self.available_cameras = None
        self.frontend_frame_queue = frontend_frame_queue
        self.camera_group_manager = CameraGroupManager(frontend_frame_queue=self.frontend_frame_queue)


    def handle_interaction(self, interaction: BaseInteraction) -> BaseResponse:
        logger.debug(f"Controller handling interaction: {interaction}")
        try:
            response = interaction.execute_command(controller=self)
            return response
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ErrorResponse.from_exception(exception=e)
