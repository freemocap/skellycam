from typing import Dict, Optional, List

import msgpack
from pydantic import BaseModel

from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]]

    @classmethod
    def create(cls, camera_ids: List[CameraId], **kwargs):
        return cls(frames={camera_id: None for camera_id in camera_ids}, **kwargs)

    @property
    def camera_ids(self) -> List[CameraId]:
        return [CameraId(camera_id) for camera_id in self.frames.keys()]

    @property
    def full(self):
        return not any([frame is None for frame in self.frames.values()])

    @property
    def oldest_timestamp_ns(self) -> Optional[int]:
        return min(
            [frame.timestamp_ns for frame in self.frames.values() if frame is not None]
        )

    def add_frame(self, frame: FramePayload):
        self.frames[frame.camera_id] = frame

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self, use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        frames_dict = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        return cls(**frames_dict)
