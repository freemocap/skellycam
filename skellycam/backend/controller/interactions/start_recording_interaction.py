from typing import Optional

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.interactions.base_models import (
    BaseRequest,
    BaseModel,
    BaseCommand,
    BaseInteraction,
)


class StartRecordingRequest(BaseRequest):
    pass


class StartRecordingResponse(BaseModel):
    pass


class StartRecordingCommand(BaseCommand):
    def execute(self, controller: "Controller", **kwargs) -> StartRecordingResponse:
        controller.camera_group_manager.start_recording()
        return StartRecordingResponse(success=True)


class StartRecordingInteraction(BaseInteraction):
    request: StartRecordingRequest
    command: Optional[StartRecordingCommand]
    response: Optional[StartRecordingResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=StartRecordingRequest.create(**kwargs))

    def execute_command(
        self, controller: "Controller", **kwargs
    ) -> StartRecordingResponse:
        self.command = StartRecordingCommand()
        self.response = self.command.execute(controller)
        return self.response
