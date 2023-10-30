from typing import Optional

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.interactions.base_models import BaseRequest, BaseResponse, BaseCommand, \
    BaseInteraction


class CloseCamerasRequest(BaseRequest):
    pass


class CloseCamerasResponse(BaseResponse):
    pass


class CloseCamerasCommand(BaseCommand):
    def execute(self, controller: "Controller", **kwargs) -> CloseCamerasResponse:
        controller.camera_group_manager.close()
        return CloseCamerasResponse(success=True)


class CloseCamerasInteraction(BaseInteraction):
    request: CloseCamerasRequest
    command: Optional[CloseCamerasCommand]
    response: Optional[CloseCamerasResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=CloseCamerasRequest.create(**kwargs))

    def execute_command(self, controller: "Controller") -> CloseCamerasResponse:
        self.command = CloseCamerasCommand()
        self.response = self.command.execute(controller)
        return self.response
