from typing import Dict, Optional

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.interactions.base_models import BaseRequest, BaseResponse, BaseCommand, \
    BaseInteraction
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId


class UpdateCameraConfigsException(Exception):
    pass


class UpdateCameraConfigsRequest(BaseRequest):
    camera_configs: Dict[CameraId, CameraConfig]

    @classmethod
    def create(cls, camera_configs: Dict[CameraId, CameraConfig]):
        return cls(camera_configs=camera_configs)


class UpdateCameraConfigsResponse(BaseResponse):
    pass


class UpdateCameraConfigsCommand(BaseCommand):
    def execute(self, controller, **kwargs) -> UpdateCameraConfigsResponse:
        try:
            camera_configs = kwargs["camera_configs"]
        except KeyError:
            raise KeyError("Missing `camera_configs` argument")

        try:
            controller.camera_group_manager.update_configs(camera_configs=camera_configs)
            return UpdateCameraConfigsResponse(success=True)
        except Exception as e:
            raise UpdateCameraConfigsException(e)


class UpdateCameraConfigsInteraction(BaseInteraction):
    request: UpdateCameraConfigsRequest
    command: Optional[UpdateCameraConfigsCommand]
    response: Optional[UpdateCameraConfigsResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=UpdateCameraConfigsRequest.create(**kwargs))

    def execute_command(self, controller: Controller, **kwargs ) -> UpdateCameraConfigsResponse:
        self.command = UpdateCameraConfigsCommand()
        self.response = self.command.execute(controller, camera_configs=self.request.camera_configs)
        return self.response
