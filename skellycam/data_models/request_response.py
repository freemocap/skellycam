from typing import Dict, Any

from pydantic import BaseModel


class Request(BaseModel):
    type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = {}


class Response(Request):
    success: bool


class UpdateModel(Request):
    type: str = "update"
    source: str
