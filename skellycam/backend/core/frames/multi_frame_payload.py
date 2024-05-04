from typing import Dict, Optional, List

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
        if len(self.frames) == 0:
            return False
        return not any([frame is None for frame in self.frames.values()])

    @property
    def oldest_timestamp_ns(self) -> Optional[int]:
        return min(
            [frame.timestamp_ns for frame in self.frames.values() if frame is not None]
        )

    def __len__(self):
        return len(self.frames)

    def __getitem__(self, key: CameraId):
        return self.frames[key]

    def __setitem__(self, key: CameraId, value: Optional[FramePayload]):
        self.frames[key] = value


    def __contains__(self, key: CameraId):
        return key in self.frames

    def __delitem__(self, key: CameraId):
        del self.frames[key]

    def __str__(self):
        frame_strs = []
        for camera_id, frame in self.frames.items():
            if frame:
                frame_strs.append(str(frame))
            else:
                frame_strs.append(f"{camera_id}: None")

        return "\n".join(frame_strs)
