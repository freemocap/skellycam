from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel

from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.frame_payloads.multiframe_timestamps import MultiframeTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.type_overloads import CameraIdString

if TYPE_CHECKING:
    from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload

class MultiFrameMetadata(BaseModel):
    multi_frame_number: int
    frame_metadatas: dict[CameraIdString, FrameMetadata]
    mf_timestamps: MultiframeTimestamps
    timebase_mapping: TimebaseMapping


    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: 'MultiFramePayload'):
        return cls(
            multi_frame_number=multi_frame_payload.multi_frame_number,
            frame_metadatas={
                camera_id: frame.frame_metadata
                for camera_id, frame in multi_frame_payload.frames.items()
            },
            timebase_mapping=multi_frame_payload.timebase_mapping,
            mf_timestamps=MultiframeTimestamps.from_multiframe(multi_frame_payload)
        )


    @property
    def timestamp_unix_seconds_local(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.timestamps.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadatas.values()
        ])
        unix_ns = self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(int(mean_frame_grab_ns), local_time=True)
        return unix_ns / 1e9
    @property
    def timestamp_unix_seconds_utc(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.timestamps.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadatas.values()
        ])
        unix_ns = self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(int(mean_frame_grab_ns), local_time=False)
        return unix_ns / 1e9

    @property
    def seconds_since_cameras_connected(self) -> float:
        return self.timestamp_unix_seconds_utc - self.timebase_mapping.utc_time_ns / 1e9

    @property
    def inter_camera_grab_range_ns(self) -> int:
        grab_times = [frame_metadata.timestamps.post_grab_timestamp_ns
                      for frame_metadata in self.frame_metadatas.values()]
        return int(np.max(grab_times) - np.min(grab_times))
