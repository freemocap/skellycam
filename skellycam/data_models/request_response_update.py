import pprint
from typing import Dict, Any, Literal

from pydantic import BaseModel, Field, root_validator

from skellycam.data_models.timestamps.timestamp import Timestamp

class Request(BaseModel):
    type: Literal["success","update","error","warning"] = Field(default="request")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Any metadata to include with this request (i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        return pprint.pformat(self.dict(), indent=4)


class Response(Request):
    success: bool

    @root_validator(pre=True)
    def set_type(cls, values):
        values["type"] = "response"
        return values


class UpdateModel(Request):
    source: str = Field(default_factory=str, description="The function/method where this update (should look like an import path, e.g. `backend.data.models.Update`)")

    @root_validator(pre=True)
    def set_type(cls, values):
        values["type"] = "update"
        return values
