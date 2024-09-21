import json
import time
from ast import Bytes
from dataclasses import dataclass
from typing import Dict, Optional, List, Any

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from skellycam.core import CameraId
from skellycam.core.frames.payloads.frame_payload import FramePayload, FramePayloadDTO
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping


class MultiFramePayload(BaseModel):
    """
    Lightweight data transfer object for MultiFramePayload
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frames: Dict[CameraId, Optional[FramePayloadDTO]]
    utc_ns_to_perf_ns: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping,
                                                       description=UtcToPerfCounterMapping.__doc__)
    multi_frame_number: int = 0
    lifespan_timestamps_ns: List[Dict[str, int]] = Field(default_factory=lambda: [{"created": time.perf_counter_ns()}])



    @classmethod
    def create_initial(cls, camera_ids: List[CameraId], ) -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in camera_ids})

    @classmethod
    def from_previous(cls, previous: 'MultiFramePayload') -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns,
                   )

    @property
    def full(self) -> bool:
        return all([frame is not None for frame in self.frames.values()])

    def to_list(self) -> List[Any]:
        if not self.full:
            raise ValueError("Cannot serialize MultiFramePayloadDTO to list without all frames present")
        ret = [b"START"]
        metadata_bytes = self.model_dump_json(exclude={"frames"}).encode("utf-8")
        ret.append(metadata_bytes)
        for frame in self.frames.values():
            ret.append(b"FRAME-START")
            ret.extend(frame.to_bytes_list())
            ret.append(b"FRAME-END")
        ret.append(b"END")
        return ret

    def add_frame(self, frame_dto: FramePayloadDTO) -> None:
        camera_id = frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]
        self.lifespan_timestamps_ns.append({
            f"add_camera_{camera_id}_frame_{frame_dto.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]}": time.perf_counter_ns()})
        self.frames[camera_id] = frame_dto

    @classmethod
    def from_list(cls, data: List[Any]) -> 'MultiFramePayload':
        metadata = json.loads(data.pop(0).decode("utf-8"))
        frames = {}
        while data[0] != b"END":
            popped = data.pop(0)
            if popped != b"FRAME-START":
                raise ValueError(f"Unexpected element in MultiFramePayloadDTO bytes list, expected 'FRAME-START', got {popped}")
            frame_list = []
            while data[0] != b"FRAME-END":
                frame_list.append(data.pop(0))
            if data.pop(0) != b"FRAME-END":
                raise ValueError(f"Unexpected element in MultiFramePayloadDTO bytes list, expected 'FRAME-END', got {popped}")
            frame = FramePayloadDTO.from_bytes_list(frame_list)
            frames[frame.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]] = frame

        return cls(frames=frames, **metadata)

    def to_metadata(self) -> 'MultiFrameMetadata':
        return MultiFrameMetadata.from_multi_frame_payload(multi_frame_payload=self)

    def __str__(self) -> str:
        print_str = f"["
        for camera_id, frame in self.frames.items():
            print_str += str(frame) + "\n"
        print_str += "]"
        return print_str

# class MultiFramePayload(BaseModel):
#     frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
#                                                            description="Synchronously captured frames from each camera")
#     utc_ns_to_perf_ns: UtcToPerfCounterMapping
#     multi_frame_number: int
#     lifespan_timestamps_ns: List[Dict[str, int]]
#
#     @property
#     def camera_ids(self) -> List[CameraId]:
#         return list(self.frames.keys())
#
#     @classmethod
#     def from_dto_list(cls, dto: MultiFramePayloadDTO) -> 'MultiFramePayload':
#         return cls(
#             frames={CameraId(camera_id): FramePayload.from_dto(frame_dto)
#                     for camera_id, frame_dto in dto.frames.items()},
#             multi_frame_number=dto.multi_frame_number,
#             utc_ns_to_perf_ns=dto.utc_ns_to_perf_ns,
#             lifespan_timestamps_ns=dto.lifespan_timestamps_ns
#         )
#
#     def to_metadata(self) -> 'MultiFrameMetadata':
#         return MultiFrameMetadata.from_multi_frame_payload(multi_frame_payload=self)
#
#     def __str__(self) -> str:
#         print_str = f"["
#         for camera_id, frame in self.frames.items():
#             print_str += str(frame) + "\n"
#         print_str += "]"
#         return print_str



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
                camera_id: FrameMetadata.from_frame_metadata_array(frame.metadata)
                for camera_id, frame in multi_frame_payload.frames.items()
            },
            multi_frame_lifespan_timestamps_ns=multi_frame_payload.lifespan_timestamps_ns,
            utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns
        )

    @property
    def timestamp_unix_seconds(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.frame_lifespan_timestamps_ns.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadata_by_camera.values()
        ])
        unix_ns = self.utc_ns_to_perf_ns.convert_perf_counter_ns_to_unix_ns(mean_frame_grab_ns)
        return unix_ns / 1e9
