import pprint
from typing import Dict, Any

from pydantic import BaseModel


class Request(BaseModel):
    type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = {}

    def __str__(self):
        return pprint.pformat(self.dict(), indent=4)


class Response(Request):
    success: bool


class UpdateModel(Request):
    type: str = "update"
    source: str
