from typing import List, Dict, Optional

from pydantic import BaseModel

from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class MultiFramePayload(BaseModel):
    frames: Dict[str, Optional[FramePayload]]

    # framerate: float = Field(description="The framerate of the camera that these frames came from")
    # force_sync: bool = Field(default=True, description="Whether to force the frames to be synchronized")

    @classmethod
    def create(cls, camera_ids: List[CameraId], **kwargs):
        return cls(frames={camera_id: None for camera_id in camera_ids},
                   **kwargs)

    # @root_validator
    # def validate_synchronization(cls, values):
    #     """
    #     Ensure that frame timestamps are within +/- 1 frame duration of each other
    #     """
    #     if not values["force_sync"]:
    #         return values
    #
    #     timestamps = [frame.timestamp_ns for frame in values["frames"].values()]
    #     if not timestamps:
    #         return values
    #
    #     min_timestamp = min(timestamps)
    #     max_timestamp = max(timestamps)
    #     frame_duration = 1 / values["framerate"]
    #     if max_timestamp-min_timestamp > frame_duration:
    #         raise ValueError(f"Timestamps are not synchronized: {timestamps}")

    @property
    def full(self):
        return not any([frame is None for frame in self.frames.values()])

    def add_frame(self, frame: FramePayload):
        self.frames[str(frame.camera_id)] = frame
