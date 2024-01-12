from typing import Optional

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.interactions.base_models import (
    BaseRequest,
    BaseModel,
    BaseCommand,
    BaseInteraction,
)


class StopRecordingRequest(BaseRequest):
    pass


class StopRecordingResponse(BaseModel):
    pass


class StopRecordingCommand(BaseCommand):
    def execute(self, controller: "Controller", **kwargs) -> StopRecordingResponse:
        controller.camera_group_manager.stop_recording()
        return StopRecordingResponse(success=True)


class StopRecordingInteraction(BaseInteraction):
    request: StopRecordingRequest
    command: Optional[StopRecordingCommand]
    response: Optional[StopRecordingResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=StopRecordingRequest.create(**kwargs))

    def execute_command(
        self, controller: "Controller", **kwargs
    ) -> StopRecordingResponse:
        self.command = StopRecordingCommand()
        self.response = self.command.execute(controller)
        return self.response
