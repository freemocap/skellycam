"""
Extracts per-camera frame lifecycle timestamps from frame recarrays
and packages them as JSON-serializable performance data for the frontend.

Structured for direct ingestion into Perspective tables on the frontend:
  - camera_lifecycle_rows: one row per camera per frame (flat, for Perspective)
  - inter_camera_sync: one row per multi-frame (inter-camera synchronization)
"""
import logging
import time

import numpy as np

from skellycam.api.websocket.websocket_message_types import WebsocketMessageType
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)

# TODO - this prob should live somewhere else, but its working fine enough here
def _ns_to_ms(ns: int | float) -> float:
    return float(ns) / 1e6


def _safe_duration_ms(start_ns: int | float, end_ns: int | float) -> float:
    if start_ns and end_ns:
        return _ns_to_ms(end_ns - start_ns)
    return -1.0


def extract_performance_data_from_frames(
    latest_frames: dict[CameraIdString, np.recarray],
    session_start_perf_ns: int,
) -> dict:
    """
    Extract per-camera frame lifecycle timestamps from the latest multi-frame.

    Returns a JSON-serializable dict structured for Perspective table ingestion.
    """
    if not latest_frames:
        raise ValueError("latest_frames must not be empty")

    frame_numbers: list[int] = []
    per_camera_rows: list[dict] = []
    grab_timestamps_ns: list[float] = []

    now_perf_ns = time.perf_counter_ns()
    timestamp_ms = _ns_to_ms(now_perf_ns - session_start_perf_ns)

    for camera_id, frame_recarray in latest_frames.items():
        metadata = frame_recarray.frame_metadata
        frame_number = int(metadata.frame_number[0])
        frame_numbers.append(frame_number)

        ts = metadata.timestamps

        # Extract lifecycle timestamps from the numpy recarray
        initialized_ns = int(ts.initialized_ns[0])
        pre_grab_ns = int(ts.pre_frame_grab_ns[0])
        post_grab_ns = int(ts.post_frame_grab_ns[0])
        pre_retrieve_ns = int(ts.pre_frame_retrieve_ns[0])
        post_retrieve_ns = int(ts.post_frame_retrieve_ns[0])
        pre_shm_ns = int(ts.pre_copy_to_camera_shm_ns[0])
        post_shm_ns = int(ts.post_copy_to_camera_shm_ns[0])
        pre_record_ns = int(ts.pre_frame_record_ns[0])
        post_record_ns = int(ts.post_frame_record_ns[0])

        grab_mid_ns = (pre_grab_ns + post_grab_ns) // 2
        grab_timestamps_ns.append(float(grab_mid_ns))

        row = {
            "timestamp_ms": round(timestamp_ms, 3),
            "frame_number": frame_number,
            "camera_id": str(camera_id),
            "grab_duration_ms": round(_safe_duration_ms(pre_grab_ns, post_grab_ns), 4),
            "idle_before_retrieve_ms": round(_safe_duration_ms(post_grab_ns, pre_retrieve_ns), 4),
            "retrieve_duration_ms": round(_safe_duration_ms(pre_retrieve_ns, post_retrieve_ns), 4),
            "idle_before_shm_copy_ms": round(_safe_duration_ms(post_retrieve_ns, pre_shm_ns), 4),
            "shm_copy_duration_ms": round(_safe_duration_ms(pre_shm_ns, post_shm_ns), 4),
            "idle_before_record_ms": round(_safe_duration_ms(post_shm_ns, pre_record_ns), 4),
            "record_duration_ms": round(_safe_duration_ms(pre_record_ns, post_record_ns), 4),
            "total_processing_ms": round(_safe_duration_ms(pre_grab_ns, post_record_ns), 4),
            "total_idle_ms": round(_safe_duration_ms(initialized_ns, pre_grab_ns), 4),
            "grab_timestamp_from_start_ms": round(_ns_to_ms(grab_mid_ns - session_start_perf_ns), 3),
        }
        per_camera_rows.append(row)

    # Inter-camera sync metrics
    grab_range_ms = 0.0
    grab_stddev_ms = 0.0
    if len(grab_timestamps_ns) > 1:
        grab_arr = np.array(grab_timestamps_ns, dtype=np.float64)
        grab_range_ms = round(_ns_to_ms(float(np.max(grab_arr) - np.min(grab_arr))), 4)
        grab_stddev_ms = round(_ns_to_ms(float(np.std(grab_arr))), 4)

    unique_frame_numbers = set(frame_numbers)
    frame_number = frame_numbers[0] if len(unique_frame_numbers) == 1 else max(frame_numbers)

    return {
        "message_type": WebsocketMessageType.PERFORMANCE_DATA,
        "frame_number": frame_number,
        "timestamp_ms": round(timestamp_ms, 3),
        "camera_lifecycle_rows": per_camera_rows,
        "inter_camera_sync": {
            "timestamp_ms": round(timestamp_ms, 3),
            "frame_number": frame_number,
            "grab_range_ms": grab_range_ms,
            "grab_stddev_ms": grab_stddev_ms,
            "num_cameras": len(latest_frames),
        },
    }
