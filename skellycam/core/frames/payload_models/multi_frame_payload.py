import time
from typing import Dict, Optional, List

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.metadata.frame_metadata import FRAME_METADATA_MODEL
from skellycam.core.frames.payload_models.frame_payload import FramePayload, FramePayloadDTO
from skellycam.utilities.utc_to_perfcounter_mapping import UtcToPerfCounterMapping


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
                                                           description="Synchronously captured frames from each camera")
    utc_ns_to_perf_ns: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping,
                                                       description=UtcToPerfCounterMapping.__doc__)
    multi_frame_number: int = 0
    lifecycle_timestamps_ns: List[Dict[str, int]] = Field(default_factory=lambda: {"created": time.perf_counter_ns()})

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
        self.lifecycle_timestamps_ns.append({
                                                f"add_camera_{frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID]}_frame_{frame_dto.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER]}": time.perf_counter_ns()})
        frame = FramePayload.from_dto(dto=frame_dto)
        self.frames[frame.camera_id] = frame

    def __str__(self) -> str:
        print_str = f"["
        for camera_id, frame in self.frames.items():
            print_str += str(frame) + "\n"
        print_str += "]"
        return print_str
