import pprint
from typing import Dict, Any, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.timestamps.timestamp import Timestamp

if TYPE_CHECKING:
    from skellycam.backend.controller.controller import Controller


class BaseMessage(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict, description="The data for this message")
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request "
                                                 "(i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        dict_str = {"name": self.__class__.__name__}
        dict_str.update(**self.dict())
        dict_str["timestamp"] = str(self.timestamp)  # use the string representation of the timestamp
        return pprint.pformat(dict_str, indent=4)


class BaseRequest(BaseMessage):
    """
    A request from the frontend to the backend
    """

    @classmethod
    def create(cls, metadata: dict = None, **kwargs, ):
        metadata = kwargs.pop("metadata", {}) if metadata is None else metadata
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
        dict_str = {"name": self.__class__.__name__}
        dict_str.update(**self.dict())
        return pprint.pformat(dict_str, indent=4)


class BaseInteraction(BaseModel):
    """
    A request from the frontend to the backend, which will be trigger a command and then return a response
    """
    request: BaseRequest
    command: Optional[BaseCommand]
    response: Optional[BaseResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=cls.request.create(**kwargs))

    def execute_command(self, controller: "Controller") -> BaseResponse:
        self.command.from_request(self.request)
        self.response = self.command.execute(controller)
        return self.response


    def __str__(self):
        dict_str = {"name": self.__class__.__name__,
                    "request": str(self.request),
                    "command": str(self.command) if self.command else f"Yet to be defined",
                    "response": str(self.response) if self.response else f"Yet to be defined"
                    }

        return pprint.pformat(dict_str, indent=4)


class DetectAvailableCamerasRequest(BaseRequest):
    """
    A request to detect available cameras and return their info in a `CamerasDetected` response
    """
    pass


class CamerasDetectedResponse(BaseResponse):
    success: bool
    available_cameras: Dict[str, CameraDeviceInfo]


class DetectAvailableCamerasCommand(BaseCommand):
    def execute(self, controller: "Controller") -> CamerasDetectedResponse:
        controller.available_cameras = detect_available_cameras()
        return CamerasDetectedResponse(success=True,
                                       available_cameras=controller.available_cameras)


class DetectCamerasInteraction(BaseInteraction):
    request: DetectAvailableCamerasRequest
    command: Optional[DetectAvailableCamerasCommand]
    response: Optional[CamerasDetectedResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=DetectAvailableCamerasRequest.create(**kwargs))

    def execute_command(self, controller: "Controller") -> CamerasDetectedResponse:
        self.command = DetectAvailableCamerasCommand()
        self.response = self.command.execute(controller)
        return self.response


class ConnectToCamerasCommand(BaseCommand):
    camera_configs: Dict[str, CameraConfig]

    def execute(self, controller):
        controller.camera_group_manager = CameraGroupManager(camera_configs=self.camera_configs)
        controller.camera_group_manager.start()


class CameraConnectedResponse(BaseModel):
    success: bool
    camera_group_manager: Any


class ErrorResponse(BaseResponse):
    error: str

    @classmethod
    def from_exception(cls, exception: Exception):
        return cls(success=False,
                   error=str(exception))
