import json
import time
from typing import Dict, Optional, List, Any

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.frames.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping
from skellycam.utilities.rotate_image import rotate_image

BYTES_BUFFER_SPLITTER = b"__SPLITTER__"

class MultiFramePayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frames: Dict[CameraId, Optional[FramePayload]]
    utc_ns_to_perf_ns: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping,
                                                       description=UtcToPerfCounterMapping.__doc__)
    # multi_frame_number: int = 0
# #     # lifespan_timestamps_ns: List[Dict[str, int]] = Field(default_factory=lambda: [{"created": time.perf_counter_ns()}])

    camera_configs: CameraConfigs

    @classmethod
    def create_initial(cls, camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in camera_configs.keys()},
                   camera_configs=camera_configs, )

    @classmethod
    def from_previous(cls,
                      previous: 'MultiFramePayload',
                      camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns,
                   camera_configs=camera_configs,
                   )

    @property
    def multi_frame_number(self) -> int:
        nums = []
        for frame in self.frames.values():
            if frame is not None:
                nums.append(frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value])
        mf_num = set(nums)
        if len(mf_num) > 1:
            raise ValueError(f"MultiFramePayloadDTO has multiple frame numbers: {mf_num}")
        return mf_num.pop()

    @property
    def full(self) -> bool:
        return all([frame is not None for frame in self.frames.values()])

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.frames.keys())

    def to_numpy_buffer(self) -> np.ndarray:
        bytes_buffer =  BYTES_BUFFER_SPLITTER.join(self.to_bytes_list())
        return np.frombuffer(bytes_buffer, dtype=np.uint8)


    @classmethod
    def from_numpy_buffer(cls, data: np.ndarray) -> 'MultiFramePayload':
        bytes_list = data.tobytes().split(BYTES_BUFFER_SPLITTER)
        return cls.from_list(bytes_list)

    @classmethod
    def from_list(cls, data: List[Any]) -> 'MultiFramePayload':
        metadata = json.loads(data.pop(0).decode("utf-8"))
        frames = {}
        while len(data) > 0:
            popped = data.pop(0)
            if popped != b"FRAME-START":
                raise ValueError(
                    f"Unexpected element in MultiFramePayloadDTO bytes list, expected 'FRAME-START', got {popped}")
            frame_list = []
            while data[0] != b"FRAME-END":
                frame_list.append(data.pop(0))
            if data.pop(0) != b"FRAME-END":
                raise ValueError(
                    f"Unexpected element in MultiFramePayloadDTO bytes list, expected 'FRAME-END', got {popped}")
            frame = FramePayload.from_bytes_list(frame_list)
            frames[frame.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]] = frame

        return cls(frames=frames, **metadata)

    def to_bytes_list(self) -> List[Any]:
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

    def add_frame(self, frame_dto: FramePayload) -> None:
        camera_id = frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]
# #         # self.lifespan_timestamps_ns.append({
        #     f"add_camera_{camera_id}_frame_{frame_dto.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]}": time.perf_counter_ns()})
        self.frames[camera_id] = frame_dto

    def get_frame(self, camera_id: CameraId, rotate: bool = True, return_copy:bool=True) -> Optional[FramePayload]:

        if return_copy:
            frame = self.frames[camera_id].model_copy()
        else:
            frame = self.frames[camera_id]

        if frame is None:
            raise ValueError(f"Cannot get frame for camera_id {camera_id} from MultiFramePayloadDTO, frame is None")

        if rotate and not self.camera_configs[camera_id].rotation == RotationTypes.NO_ROTATION:
            frame.image = rotate_image(frame.image, self.camera_configs[camera_id].rotation)

        return frame

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
    # multi_frame_lifespan_timestamps_ns: List[Dict[str, int]]  # TODO - Make a model for this

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload):
        return cls(
            frame_number=multi_frame_payload.multi_frame_number,
            frame_metadata_by_camera={
                camera_id: FrameMetadata.from_frame_metadata_array(frame.metadata)
                for camera_id, frame in multi_frame_payload.frames.items()
            },
            # multi_frame_lifespan_timestamps_ns=multi_frame_payload.lifespan_timestamps_ns,
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

