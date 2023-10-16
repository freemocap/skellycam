import pprint
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

from skellycam.backend.controller.controller import Controller
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.timestamps.timestamp import Timestamp


class BaseMessage(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict, description="The data for this message")
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request "
                                                 "(i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        dict_str = self.dict()
        dict_str["timestamp"] = str(self.timestamp)  # use the string representation of the timestamp
        return pprint.pformat(dict_str, indent=4)


class BaseRequest(BaseMessage):
    """
    A request from the frontend to the backend
    """

    @classmethod
    def create(cls, **kwargs):
        metadata = kwargs.pop("metadata", {})
        return cls(data=kwargs,
                   metadata=metadata)


class BaseResponse(BaseMessage):
    """
    A response from the backend to the frontend
    """
    success: bool = Field(default=False, description="Whether or not this request was successful")



class BaseCommand(BaseModel):
    @classmethod
    def from_request(cls, request: BaseRequest):
        raise NotImplementedError

    def execute(self, controller) -> BaseResponse:
        raise NotImplementedError

    def __str__(self):
        dict_str = self.dict()
        return pprint.pformat(dict_str, indent=4)


class BaseInteraction(BaseModel):
    """
    A request from the frontend to the backend, which will be trigger a command and then return a response
    """
    request: BaseRequest
    command:  Optional[BaseCommand]
    response: Optional[BaseResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=cls.request.create(**kwargs,
                                              metadata=kwargs.pop("metadata", {})
                                              )
                   )
    def execute_command(self, controller: Controller):
        self.command.from_request(self.request)
        self.response = self.command.execute(controller)


class DetectAvailableCameras(BaseRequest):
    """
    A request to detect available cameras and return their info in a `CamerasDetected` response
    """
    pass

class CamerasDetected(BaseResponse):
    success: bool
    available_cameras: Dict[str, CameraDeviceInfo]

class DetectAvailableCamerasCommand(BaseCommand):
    def execute(self, controller: Controller) -> BaseResponse:
        controller.available_cameras = detect_available_cameras()
        return CamerasDetected(success=True,
                               available_cameras=controller.available_cameras)
class DetectCameras(BaseInteraction):
    request: DetectAvailableCameras
    command: Optional[DetectAvailableCamerasCommand]
    response: Optional[CamerasDetected]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=cls.request.create())

    def execute_command(self, controller: Controller):
        self.command = DetectAvailableCamerasCommand()
        self.command.execute(controller)
        self.response = CamerasDetected(success=True,
                                        available_cameras=controller.available_cameras)



class ConnectToCamerasCommand(BaseCommand):
    camera_configs: Dict[str, CameraConfig]

    def execute(self, controller):
        controller.camera_group_manager = CameraGroupManager(camera_configs=self.camera_configs)
        controller.camera_group_manager.start()


class CameraConnectedResponse(BaseModel):
    success: bool
    camera_group_manager: Any
