from skellycam.system.environment.get_logger import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.interactions.base_models import BaseInteraction, BaseResponse, \
    ErrorResponse

CONTROLLER = None


def get_or_create_controller(frontend_frame_pipe_sender  # multiprocessing.connection.Connection
                             ) -> 'Controller':
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller(frontend_frame_pipe_sender=frontend_frame_pipe_sender)
    return CONTROLLER


class Controller:

    def __init__(self,
                 frontend_frame_pipe_sender  # multiprocessing.connection.Connection
                 ) -> None:
        self.available_cameras = None
        self.frontend_frame_pipe_sender = frontend_frame_pipe_sender
        self.camera_group_manager = CameraGroupManager(
            frontend_frame_pipe_sender=self.frontend_frame_pipe_sender)

    def handle_interaction(self, interaction: BaseInteraction) -> BaseResponse:
        logger.debug(f"Controller handling interaction: {interaction}")
        try:
            response = interaction.execute_command(controller=self)
            return response
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ErrorResponse.from_exception(exception=e)
