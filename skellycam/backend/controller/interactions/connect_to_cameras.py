import traceback
from typing import Dict, Optional

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.interactions.base_models import BaseCommand, BaseRequest, \
    BaseInteraction, BaseResponse
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.system.environment.get_logger import logger


class ConnectToCamerasRequest(BaseRequest):
    camera_configs: Dict[CameraId, CameraConfig]

    @classmethod
    def create(cls, camera_configs: Dict[CameraId, CameraConfig]):
        if len(camera_configs) == 0:
            raise ValueError("Must have at least one camera")
        return cls(camera_configs=camera_configs)


class ConnectToCamerasResponse(BaseResponse):
    pass


class ConnectToCamerasCommand(BaseCommand):
    camera_configs: Dict[CameraId, CameraConfig]

    def execute(self,
                controller: Controller,
                **kwargs) -> ConnectToCamerasResponse:
        try:
            camera_configs = kwargs.get('camera_configs')
            controller.camera_group_manager.start(camera_configs=camera_configs)
            return ConnectToCamerasResponse(success=True)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            return ConnectToCamerasResponse(success=False,
                                            metadata={"error": str(e),
                                                      "traceback": str(traceback.format_exc())})


class ConnectToCamerasInteraction(BaseInteraction):
    request: ConnectToCamerasRequest
    command: Optional[ConnectToCamerasCommand]
    response: Optional[ConnectToCamerasResponse]

    @classmethod
    def as_request(cls, camera_configs: Dict[CameraId, CameraConfig]):
        return cls(request=ConnectToCamerasRequest.create(camera_configs=camera_configs))

    def execute_command(self, controller: Controller, **kwargs) -> BaseResponse:
        self.command = ConnectToCamerasCommand(camera_configs=self.request.camera_configs)
        self.response = self.command.execute(controller=controller,
                                             camera_configs=self.request.camera_configs)
        return self.response
