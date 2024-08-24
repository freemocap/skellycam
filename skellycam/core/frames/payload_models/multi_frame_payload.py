import time
from typing import Dict, Optional, List

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.payload_models.frame_payload import FramePayload, FramePayloadDTO
from skellycam.core.frames.payload_models.metadata.frame_metadata import FrameMetadata
from skellycam.core.frames.payload_models.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
                                                           description="Synchronously captured frames from each camera")
    utc_ns_to_perf_ns: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping,
                                                       description=UtcToPerfCounterMapping.__doc__)
    multi_frame_number: int = 0
    lifespan_timestamps_ns: List[Dict[str, int]] = Field(default_factory=lambda: [{"created": time.perf_counter_ns()}])

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
        self.lifespan_timestamps_ns.append({
            f"add_camera_{frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]}_frame_{frame_dto.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]}": time.perf_counter_ns()})
        frame = FramePayload.from_dto(dto=frame_dto)
        self.frames[frame.camera_id] = frame

    def to_metadata(self) -> 'MultiFrameMetadata':
        return MultiFrameMetadata.from_multi_frame_payload(multi_frame_payload=self)

    def __str__(self) -> str:
        print_str = f"["
        for camera_id, frame in self.frames.items():
            print_str += str(frame) + "\n"
        print_str += "]"
        return print_str


class MultiFrameMetadata(BaseModel):
    frame_number: int
    frame_metadata_by_camera: Dict[CameraId, FrameMetadata]
    utc_ns_to_perf_ns: UtcToPerfCounterMapping
    multi_frame_lifespan_timestamps_ns: List[Dict[str, int]]  # TODO - Make a model for this

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload):
        return cls(
            frame_number=multi_frame_payload.multi_frame_number,
            frame_metadata_by_camera={
                camera_id: FrameMetadata.from_array(frame.metadata)
                for camera_id, frame in multi_frame_payload.frames.items()
            }
        )

    @property
    def timestamp_unix_seconds(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadata_by_camera.values()
        ]) / 1e9

        return self.utc_ns_to_perf_ns.convert_perf_counter_ns_to_unix_ns(mean_frame_grab_ns) / 1e9
