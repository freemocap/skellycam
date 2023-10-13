import pprint
from enum import Enum
from typing import Dict, Any

from pydantic import BaseModel, Field, root_validator

from skellycam.data_models.timestamps.timestamp import Timestamp


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    UPDATE = "update"
    ERROR = "error"
    WARNING = "warning"





class Request(BaseModel):
    message_type: MessageType = Field(default=MessageType.REQUEST, description="The type of request")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request (i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        dict_str = self.dict()
        dict_str["timestamp"] = str(self.timestamp)  # use the string representation of the timestamp
        return pprint.pformat(dict_str, indent=4)


class Response(Request):
    success: bool

    @root_validator(pre=True)
    def set_type(cls, values):
        values["message_type"] = MessageType.RESPONSE
        return values



class UpdateModel(Request):
    source: str = Field(default_factory=str,
                        description="The function/method where this update (should look like an import path, e.g. `backend.data.models.Update`)")

    @root_validator(pre=True)
    def set_type(cls, values):
        values["message_type"] = MessageType.UPDATE
        return values
