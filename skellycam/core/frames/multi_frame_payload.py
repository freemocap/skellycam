import time
from typing import Dict, Optional, List

from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]] = Field(default_factory=dict,
                                                           description="A mapping of camera_id to FramePayload")
    utc_ns_to_perf_ns: Dict[str, int] = Field(
        description="A mapping of `time.time_ns()` to `time.perf_counter_ns()` "
                    "to allow conversion of `time.perf_counter_ns()`'s arbitrary "
                    "time base to unix time")
    logs: List[str] = Field(default_factory=list,
                            description="Lifecycle events for this payload, "
                                        "format: f'{event_name}:{perf_counter_ns}'")
    multi_frame_number: int = 0

    @property
    def full(self):
        return all([frame is not None for frame in self.frames.values()])

    @property
    def hydrated(self):
        return all([frame.hydrated for frame in self.frames.values()])

    @classmethod
    def create(cls,
               camera_ids: List[CameraId] = None,
               multi_frame_number: int = 0,
               ) -> 'MultiFramePayload':

        if camera_ids is None:
            camera_ids = []
        utc_ns = time.time_ns()
        perf_ns = time.perf_counter_ns()
        return cls(frames={CameraId(camera_id): None for camera_id in camera_ids},
                   utc_ns_to_perf_ns={"time.time_ns": int(utc_ns), "time.perf_counter_ns": int(perf_ns)},
                   logs=[f"created:{perf_ns}"],
                   multi_frame_number=multi_frame_number
                   )

    @classmethod
    def from_previous(cls, previous: 'MultiFramePayload'):
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   multi_frame_number=previous.multi_frame_number + 1,
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns,
                   logs=[f"created_from_previous:{time.perf_counter_ns()}"]
                   )

    def add_frame(self, frame: FramePayload):
        if self.multi_frame_number > 0:
            if frame.camera_id not in self.frames.keys():
                raise ValueError(f"Camera ID {frame.camera_id} not in MultiFramePayload")
        self.frames[frame.camera_id] = frame

    def add_log(self, log: str):
        self.logs.append(f"{log}:{time.perf_counter_ns()}")

    def __str__(self):
        print_str = f""

        for camera_id, frame in self.frames.items():
            print_str += str(frame) + "\n"
        return print_str