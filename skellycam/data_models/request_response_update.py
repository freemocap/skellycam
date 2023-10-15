import pprint
from enum import Enum
from typing import Dict, Any

from pydantic import BaseModel, Field, root_validator

from skellycam.data_models.timestamps.timestamp import Timestamp


class MessageTypes(Enum):
    UNSPECIFIED = "unspecified"
    REQUEST = "request"
    RESPONSE = "response"
    UPDATE = "update"
    ERROR = "error"
    WARNING = "warning"

    SESSION_STARTED = "session_started"
    CAMERA_DETECTED = "camera_detected"
    CAMERA_CONNECTED = "camera_connected"

    DETECT_AVAILABLE_CAMERAS = "detect_available_cameras"
    UPDATE_CAMERA_CONFIGS = "update_camera_configs"
    CONNECT_TO_CAMERAS = "connect_to_cameras"
    CLOSE_CAMERAS = "close_cameras"
    START_RECORDING = "start_recording"
    STOP_RECORDING = "stop_recording"


class BaseMessage(BaseModel):
    message_type: MessageTypes = Field(default=MessageTypes.REQUEST, description="The type of request")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request "
                                                 "(i.e. stuff that might be useful, but which shouldn't be in `data`")

    @root_validator()
    def check_data(cls, values):
        """
        Check that the `data` field contains the correct keys for the given event type
        """
        match values.get("message_type", MessageTypes.UNSPECIFIED):
            case MessageTypes.CAMERA_DETECTED:
                assert "camera_configs" in values["data"], "camera_configs must be in data for CAMERA_DETECTED"
            case MessageTypes.CAMERA_CONNECTED:
                assert "image_queue" in values["data"], "image_queue must be in data for CAMERA_CONNECTED"
            case MessageTypes.UPDATE_CAMERA_CONFIGS:
                assert "camera_configs" in values["data"], "camera_configs must be in data for UPDATE_CAMERA_CONFIGS"
            case MessageTypes.START_RECORDING:
                assert "save_path" in values["data"], "save_path must be in data for START_RECORDING"

        return values

    def __str__(self):
        dict_str = self.dict()
        dict_str["timestamp"] = str(self.timestamp)  # use the string representation of the timestamp
        return pprint.pformat(dict_str, indent=4)


class Request(BaseMessage):
    @root_validator(pre=True)
    def set_type(cls, values):
        if "message_type" not in values:
            values["message_type"] = MessageTypes.REQUEST
        return values


class Response(Request):
    success: bool

    @root_validator(pre=True)
    def set_type(cls, values):
        if "message_type" not in values:
            values["message_type"] = MessageTypes.RESPONSE
        return values


class Update(Request):
    source: str = Field(default_factory=str,
                        description="The function/method where this update"
                                    " (should look like an import path,"
                                    " e.g. `backend.data.models.Update`)")

    @root_validator(pre=True)
    def set_type(cls, values):
        if "message_type" not in values:
            values["message_type"] = MessageTypes.UPDATE
        return values
