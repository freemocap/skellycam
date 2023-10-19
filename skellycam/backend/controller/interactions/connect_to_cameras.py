from typing import Dict, Optional

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.interactions.base_models import BaseCommand, BaseRequest, \
    BaseInteraction, BaseResponse
from skellycam.models.cameras.camera_config import CameraConfig

class ConnectToCamerasResponse(BaseResponse):
    pass

class ConnectToCamerasCommand(BaseCommand):
    camera_configs: Dict[str, CameraConfig]

    def execute(self, controller, **kwargs) -> ConnectToCamerasResponse:
        try:
            if controller.camera_group_manager is not None:
                controller.camera_group_manager.stop_camera_group()

            controller.camera_group_manager = CameraGroupManager(camera_configs=self.camera_configs,
                                                                 frontend_frame_queue=controller.frontend_frame_queue)
            controller.camera_group_manager.start()
            return ConnectToCamerasResponse(success=True)
        except Exception as e:
            return ConnectToCamerasResponse(success=False,
                                            error=str(e))


class ConnectToCamerasRequest(BaseRequest):
    camera_configs: Dict[str, CameraConfig]

    @classmethod
    def create(cls, camera_configs: Dict[str, CameraConfig]):
        return cls(camera_configs=camera_configs)


class ConnectToCamerasInteraction(BaseInteraction):
    request: ConnectToCamerasRequest
    command: Optional[ConnectToCamerasCommand]
    response: Optional[ConnectToCamerasResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=ConnectToCamerasRequest.create(**kwargs))

    def execute_command(self, controller: "Controller") -> BaseResponse:
        self.command = ConnectToCamerasCommand(camera_configs=self.request.camera_configs)
        self.response = self.command.execute(controller)
        return self.response


