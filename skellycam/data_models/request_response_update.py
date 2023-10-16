import multiprocessing
import pprint
from typing import Dict, Any

from pydantic import BaseModel, Field

from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.timestamps.timestamp import Timestamp


class BaseMessage(BaseModel):
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


class Response(Request):
    """
    A response to a request
    """

    success: bool


class CamerasDetected(Response):
    available_camera_devices: Dict[str, CameraDeviceInfo] = Field(default_factory=dict,
                                                                  description="A dictionary with the available"
                                                                              " cameras (as `CameraDeviceInfo`objects),"
                                                                              " keyed by camera_id")

class ConnectToCameras(Request):
    """
    A request to connect to cameras and return a multiprocessing Queue that will be used to send images
    """
    camera_configs: Dict[str, CameraConfig] = Field(default_factory=dict,
                                                    description="A dictionary with the camera configs containing the "
                                                                "information we'l give to OpenCV to connect to the "
                                                                "camera, keyed by camera_id")

class CameraConnected(Response):
    """
    A response to a `ConnectToCameras` request
    """
    image_queue: multiprocessing.Queue = Field(default_factory=multiprocessing.Queue,
                                                  description="A multiprocessing Queue that will be used to send images "
                                                                "to the frontend")
