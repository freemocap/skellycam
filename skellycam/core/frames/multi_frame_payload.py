import logging
from typing import Dict, Optional, List
from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload, FramePayloadDTO
from skellycam.utilities.utc_to_perfcounter_mapping import UtcToPerfCounterMapping

logger = logging.getLogger(__name__)

class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
                                                           description="Synchronously captured frames from each camera")
    utc_ns_to_perf_ns: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping,
                                                       description=UtcToPerfCounterMapping.__doc__)
    multi_frame_number: int = 0

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.frames.keys())

    @property
    def full(self) -> bool:
        return all([frame is not None for frame in self.frames.values()])

    @classmethod
    def create_initial(cls, camera_ids: List[CameraId], ) -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in camera_ids})

    @classmethod
    def from_previous(cls, previous: 'MultiFramePayload') -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns,
                   )

    def add_frame(self, frame_dto: FramePayloadDTO) -> None:
        frame = FramePayload.from_dto(dto=frame_dto)
        self.frames[frame.camera_id] = frame

    def set_timestamps(self, metadata_index: int, timestamp_ns: int) -> None:
        for camera_id, frame_payload in self.frames.items():
            if frame_payload is None:
                logger.warning(f"Camera {camera_id} has no frame in MultiFramePayload")
                continue
            frame_payload.metadata[metadata_index] = timestamp_ns

    def __str__(self) -> str:
        print_str = f""
        for camera_id, frame in self.frames.items():
            print_str += str(frame) + "\n"
        return print_str
