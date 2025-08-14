from typing import TypedDict

from skellycam.core.types.numpy_record_dtypes import StatsArray, IntArray
from skellycam.core.types.type_overloads import CameraIdString
# TODO - These Typed Dicts aren't quite right, but the computation seems to be fine. NEEDS FIXED!!!


class StatsDict(TypedDict):
    timestamp_midpoint: StatsArray
    timestamps: dict[str, StatsArray]
    durations: dict[str, StatsArray]
    frame_numbers: IntArray
    recording_start_time_ns: int
    camera_ids: list[CameraIdString]


class SummaryStatsDict(TypedDict):
    recording_name: str
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    framerate_stats: dict[str, float]
    frame_duration_stats: dict[str, float]
    inter_camera_grab_range_ms: dict[str, float]
    # Duration fields used in generate_text_report
    during_frame_grab_ms: dict[str, float]
    idle_before_retrieve_ms: dict[str, float]
    during_frame_retrieve_ms: dict[str, float]
    idle_before_copy_to_camera_shm_ms: dict[str, float]
    during_copy_to_camera_shm_ms: dict[str, float]
    idle_before_frame_record_ms: dict[str, float]
    during_frame_record_ms: dict[str, float]
    total_frame_processing_time_ms: dict[str, float]
    total_camera_idle_time_ms: dict[str, float]
