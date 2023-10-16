import multiprocessing
import pprint
from typing import Dict, Any

from pydantic import BaseModel, Field, root_validator

from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.timestamps.timestamp import Timestamp


class BaseMessage(BaseModel):
    data: Dict[str,Any] = Field(default_factory=dict, description="The data for this request/response/update")
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request "
                                                 "(i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        dict_str = self.dict()
        dict_str["timestamp"] = str(self.timestamp)  # use the string representation of the timestamp
        return pprint.pformat(dict_str, indent=4)


class Request(BaseMessage):
    """
    A request to do something (e.g. detect available cameras, connect to cameras, etc.)
    """
    pass


class DetectAvailableCameras(Request):
    """
    A request to detect available cameras and return their info in a `CamerasDetected` response
    """
    pass


class Update(Request):
    """
    A request to update something (e.g. a camera config, a GUI window, etc.)
    """
    source: str = Field(default_factory=str,
                        description="The function/method where this update"
                                    " (should look like an import path,"
                                    " e.g. `backend.data.models.Update`)")

class UpdateCameraConfigs(Update):
    """
    A request to update the camera configs
    """
    @root_validator
    def check_data(cls, values):
        if "camera_configs" not in values["data"]:
            raise ValueError("No `camera_configs` key in `data`")
        return values


class Response(Request):
    """
    A response to a request
    """

    success: bool


class CamerasDetected(Response):
    """
    A response to a `DetectAvailableCameras` request, should contain a list of `CameraDeviceInfo` objects
    """
    @root_validator
    def check_data(cls, values):
        if "available_cameras" not in values["data"]:
            raise ValueError("No `available_cameras` key in `data`")
        return values

class ConnectToCameras(Request):
    """
    A request to connect to cameras
    """
    @root_validator
    def check_data(cls, values):
        if "camera_configs" not in values["data"]:
            raise ValueError("No `camera_configs` key in `data`")
        return values

class CameraConnected(Response):
    """
    A response to a `ConnectToCameras` request
    """

