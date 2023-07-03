from typing import Dict

from pydantic import BaseModel

from skellycam.detection.models.frame_payload import FramePayload


class MultiFramePayload(BaseModel):
    frames: Dict[str, FramePayload]
    statistics: Dict[str, Dict[str, float] ]=None
    synchronized: bool = False
    multi_frame_number: int = -1

    class Config:
        arbitrary_types_allowed = True
