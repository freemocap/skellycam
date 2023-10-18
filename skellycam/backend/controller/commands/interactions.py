import pprint
from typing import Dict, Any, Optional, TYPE_CHECKING, Union

from pydantic import BaseModel, Field

from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.timestamps.timestamp import Timestamp

if TYPE_CHECKING:
    from skellycam.backend.controller.backendcontroller import BackendController


class BaseMessage(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict, description="The data for this message")
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request "
                                                 "(i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        return self.__class__.__name__



class BaseRequest(BaseMessage):
    """
    A request from the frontend to the backend
    """

    @classmethod
    def create(cls, **kwargs):
        return cls(**kwargs)


class BaseResponse(BaseMessage):
    """
    A response from the backend to the frontend
    """
    success: bool = Field(default=False, description="Whether or not this request was successful")

    def __str__(self):
        return f"{self.__class__.__name__}: success = {self.success}"


class ErrorResponse(BaseResponse):
    error: str

    @classmethod
    def from_exception(cls, exception: Exception):
        return cls(success=False,
                   error=str(exception))


class BaseCommand(BaseModel):
    @classmethod
    def from_request(cls, request: BaseRequest):
        raise NotImplementedError

    def execute(self, controller: 'BackendController', **kwargs) -> BaseResponse:
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

    def execute_command(self, controller: "BackendController") -> BaseResponse:
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
    def execute(self, controller: "BackendController", **kwargs) -> CamerasDetectedResponse:
        controller.available_cameras = detect_available_cameras()
        return CamerasDetectedResponse(success=True,
                                       available_cameras=controller.available_cameras)


class ConnectToCamerasResponse(BaseResponse):
    pass


class ConnectToCamerasCommand(BaseCommand):
    camera_configs: Dict[str, CameraConfig]

    def execute(self, controller, **kwargs) -> ConnectToCamerasResponse:
        try:
            controller.camera_group_manager = CameraGroupManager(camera_configs=self.camera_configs)
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

    def execute_command(self, controller: "BackendController") -> BaseResponse:
        self.command = ConnectToCamerasCommand(camera_configs=self.request.camera_configs)
        self.response = self.command.execute(controller)
        return self.response


class DetectCamerasInteraction(BaseInteraction):
    request: DetectAvailableCamerasRequest
    command: Optional[DetectAvailableCamerasCommand]
    response: Optional[CamerasDetectedResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=DetectAvailableCamerasRequest.create(**kwargs))

    def execute_command(self, controller: "BackendController") -> CamerasDetectedResponse:
        self.command = DetectAvailableCamerasCommand()
        self.response = self.command.execute(controller)
        return self.response


class CloseCamerasRequest(BaseRequest):
    pass


class CloseCamerasResponse(BaseResponse):
    pass


class CloseCamerasCommand(BaseCommand):
    def execute(self, controller, **kwargs) -> CloseCamerasResponse:
        controller.camera_group_manager.stop_camera_group()
        return CloseCamerasResponse(success=True)


class CloseCamerasInteraction(BaseInteraction):
    request: CloseCamerasRequest
    command: Optional[CloseCamerasCommand]
    response: Optional[CloseCamerasResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=CloseCamerasRequest.create(**kwargs))

    def execute_command(self, controller: "BackendController") -> CloseCamerasResponse:
        self.command = CloseCamerasCommand()
        self.response = self.command.execute(controller)
        return self.response


class UpdateCameraConfigsRequest(BaseRequest):
    camera_configs: Dict[str, CameraConfig]

    @classmethod
    def create(cls, camera_configs: Dict[str, CameraConfig]):
        return cls(camera_configs=camera_configs)


class UpdateCameraConfigsResponse(BaseResponse):
    pass


class UpdateCameraConfigsException(Exception):
    pass



class UpdateCameraConfigsCommand(BaseCommand):
    def execute(self, controller,**kwargs) -> UpdateCameraConfigsResponse:
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

    def execute_command(self, controller: "BackendController") -> UpdateCameraConfigsResponse:
        self.command = UpdateCameraConfigsCommand()
        self.response = self.command.execute(controller, camera_configs=self.request.camera_configs)
        return self.response
