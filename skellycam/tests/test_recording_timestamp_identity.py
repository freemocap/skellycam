"""Recording CSV identities must survive independently ordered input mappings."""

import asyncio
import csv
from pathlib import Path

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.numpy_timestamps.process_and_save_recording_timestamps import (
    process_and_save_recording_timestamps,
)
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE


def metadata_by_camera():
    mapping = TimebaseMapping(utc_time_ns=1_700_000_000_000_000_000,
                              perf_counter_ns=1_000_000_000, local_time_utc_offset=0)
    result = {}
    for camera_id, offset in (("7599", 0), ("ef51", 4_000_000)):
        frames = []
        for index in range(3):
            frame = np.zeros(1, dtype=FRAME_METADATA_DTYPE).view(np.recarray)
            frame.camera_info.camera_id = camera_id
            frame.frame_number = 166 + index
            frame.timebase_mapping = mapping.to_numpy_record_array()
            midpoint = 1_000_000_000 + offset + index * 33_000_000
            for field_index, name in enumerate(frame.timestamps.dtype.names):
                frame.timestamps[name] = midpoint + (field_index - 1) * 100
            frames.append(frame)
        result[camera_id] = frames
    return result


@pytest.mark.parametrize("config_order", [("7599", "ef51"), ("ef51", "7599")])
def test_saved_timestamps_follow_camera_identity(tmp_path: Path, config_order):
    metadata = metadata_by_camera()
    configs = {camera: CameraConfig(camera_id=camera, camera_index=index)
               for index, camera in enumerate(config_order)}
    recording = RecordingInfo(recording_name="identity", recording_directory=str(tmp_path))
    asyncio.run(process_and_save_recording_timestamps(metadata, configs, recording))

    assert list(metadata) == ["7599", "ef51"]
    assert list(configs) == list(config_order)
    for camera, frames in metadata.items():
        with open(recording.camera_timestamps_file_path_from_camera_id(camera), newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert [int(row["connection_frame_number"]) for row in rows] == [166, 167, 168]
        expected = [(int(frame.timestamps.pre_frame_grab_ns[0]) +
                     int(frame.timestamps.post_frame_grab_ns[0])) // 2 for frame in frames]
        assert [int(row["timestamp.perf_counter_ns.ns"]) for row in rows] == expected


@pytest.mark.parametrize("config_ids", [("7599",), ("7599", "ef51", "extra"), ("7599", "other")])
def test_mismatched_camera_sets_fail_before_export(tmp_path: Path, config_ids):
    configs = {camera: CameraConfig(camera_id=camera, camera_index=index)
               for index, camera in enumerate(config_ids)}
    recording = RecordingInfo(recording_name="invalid", recording_directory=str(tmp_path))
    with pytest.raises(ValueError, match="Camera IDs.*metadata.*config"):
        asyncio.run(process_and_save_recording_timestamps(metadata_by_camera(), configs, recording))
    assert not list(tmp_path.rglob("*.csv"))
