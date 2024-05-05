import time
from typing import Dict, Optional, List

import msgpack
from pydantic import BaseModel, Field

from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]]
    utc_ns_to_perf_ns: Dict[str, int] = Field(
        description="A mapping of `time.time_ns()` to `time.perf_counter_ns()` "
                    "to allow conversion of `time.perf_counter_ns()`'s arbitrary "
                    "time base to unix time")
    logs: List[str] = Field(default_factory=list,
                            description="Lifecycle events for this payload, "
                                        "format: f'{event_name}:{perf_counter_ns}'")
    multi_frame_number: int = 0

    @classmethod
    def create(cls,
               camera_ids: List[CameraId],
               **kwargs):
        utc_ns = time.time_ns()
        perf_ns = time.perf_counter_ns()
        return cls(frames={camera_id: None for camera_id in camera_ids},
                   utc_ns_to_perf_ns={"time.time_ns": int(utc_ns), "time.perf_counter_ns": int(perf_ns)},
                   timestamp_trace_ns=cls.init_logs(),
                   **kwargs
                   )

    @classmethod
    def from_previous(cls, previous: 'MultiFramePayload'):
        return cls(frames={camera_id: None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns.copy(),
                   timestamp_trace_ns=cls.init_logs(from_previous=True),
                   )

    @property
    def camera_ids(self) -> List[CameraId]:
        self.log("check_camera_ids")
        return [CameraId(camera_id) for camera_id in self.frames.keys()]

    @property
    def full(self):
        self.log("check_if_full")
        if len(self.frames) == 0:
            return False
        return not any([frame is None for frame in self.frames.values()])

    @property
    def oldest_timestamp_ns(self) -> Optional[int]:
        self.log("check_oldest_timestamp")
        return min(
            [frame.timestamp_ns for frame in self.frames.values() if frame is not None]
        )

    def log(self, event_name: str, add_timestamp=True):
        if add_timestamp:
            self.logs.append(f"{event_name}:{time.perf_counter_ns()}")
        else:
            self.logs.append(event_name)

    @staticmethod
    def init_logs(from_previous: bool = False):
        if from_previous:
            return [f"created_from_previous:{time.perf_counter_ns()}"]
        else:
            return [f"created:{time.perf_counter_ns()}"]

    def to_msgpack(self) -> bytes:
        self.log("to_msgpack")
        return msgpack.packb(self.dict(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        received_event = f"before_unpacking_msgpack:{time.perf_counter_ns()}"
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        instance = cls(**unpacked)
        instance.log(received_event, add_timestamp=False)
        instance.log("created_from_msgpack")
        return instance

    def __len__(self):
        self.log("check_length")
        return len(self.frames)

    def __getitem__(self, key: CameraId):
        self.log(f"get_{key}")
        return self.frames[key]

    def __setitem__(self, key: CameraId, value: Optional[FramePayload]):
        self.log(f"set_{key}")
        if self.full:
            self.log("payload_full")
        self.frames[key] = value

    def __contains__(self, key: CameraId):
        self.log(f"lookup_{key}")
        return key in self.frames

    def __delitem__(self, key: CameraId):
        self.log(f"deleted_{key}")
        del self.frames[key]

    def __str__(self):
        self.log("cast_to_str")
        frame_strs = []
        for camera_id, frame in self.frames.items():
            if frame:
                frame_strs.append(str(frame))
            else:
                frame_strs.append(f"{camera_id}: None")

        return ",".join(frame_strs)
