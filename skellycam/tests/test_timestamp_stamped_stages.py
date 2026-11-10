"""Recording timestamp files report only lifecycle events the capture backend stamped.

The OpenCV backend stamps all nine lifecycle timestamps. The Rust backend stamps only the
frame-grab bracket (the capture loop starts waiting for the next frame / the next frame is
available to the loop); its own lifecycle stays in its per-camera timing CSV. No column,
statistic or report line may describe an event that did not happen.
"""
import asyncio
import csv
import json
from pathlib import Path

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.numpy_timestamps.process_and_save_recording_timestamps import (
    process_and_save_recording_timestamps,
)
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import (
    CAMERA_TIMESTAMPS_CSV_ROW_DTYPE,
    FRAME_METADATA_DTYPE,
    MULTI_FRAME_TIMESTAMP_CSV_ROW,
)

MAPPING = TimebaseMapping(utc_time_ns=1_700_000_000_000_000_000, perf_counter_ns=1_000_000_000,
                          local_time_utc_offset=0)
STAGE_PREFIXES = ("frame.", "duration.", "total.")
GRAB_BRACKET = {"pre_frame_grab_ns", "post_frame_grab_ns"}
UNSTAMPED_STAGE_STATS = {
    "idle_before_frame_grab_ms", "idle_before_retrieve_ms", "during_frame_retrieve_ms",
    "idle_before_copy_to_camera_shm_ms", "during_copy_to_camera_shm_ms", "idle_before_frame_record_ms",
    "during_frame_record_ms", "total_frame_processing_time_ms", "total_camera_idle_time_ms",
}


def metadata(stamped_fields):
    result = {}
    for camera_index, camera_id in enumerate(("cam0", "cam1")):
        frames = []
        for index in range(5):
            frame = np.zeros(1, dtype=FRAME_METADATA_DTYPE).view(np.recarray)
            frame.camera_info.camera_id = camera_id
            frame.camera_info.camera_index = camera_index
            frame.frame_number = index
            frame.timebase_mapping = MAPPING.to_numpy_record_array()
            start = 1_000_000_000 + camera_index * 2_000_000 + index * 33_000_000
            for offset, name in enumerate(frame.timestamps.dtype.names):
                if name in stamped_fields:
                    frame.timestamps[name] = start + offset * 1_000_000
            frames.append(frame)
        result[camera_id] = frames
    return result


def finalize(tmp_path, frames):
    configs = {camera: CameraConfig(camera_id=camera, camera_index=index) for index, camera in enumerate(frames)}
    recording = RecordingInfo(recording_name="stages", recording_directory=str(tmp_path))
    asyncio.run(process_and_save_recording_timestamps(frames, configs, recording))
    return recording


def header(path):
    with open(path, newline="") as stream:
        return next(csv.reader(stream))


def test_fully_stamped_recording_reports_every_stage(tmp_path: Path):
    recording = finalize(tmp_path, metadata(set(FRAME_METADATA_DTYPE["timestamps"].names)))

    assert header(recording.camera_timestamps_file_path_from_camera_id("cam0")) == list(
        CAMERA_TIMESTAMPS_CSV_ROW_DTYPE.names)
    assert header(recording.timestamp_file_path) == list(MULTI_FRAME_TIMESTAMP_CSV_ROW.names)
    report = Path(recording.timestamp_stats_text_file_path).read_text(encoding="utf-8")
    assert "During copy to camera SHM" in report and "TOTAL FRAME PROCESSING TIME" in report
    stats = json.loads(Path(recording.timestamp_stats_json_file_path).read_text(encoding="utf-8"))
    assert UNSTAMPED_STAGE_STATS < set(stats)


def test_grab_bracket_only_reports_no_unstamped_event(tmp_path: Path):
    frames = metadata(GRAB_BRACKET)
    recording = finalize(tmp_path, frames)

    base = [name for name in CAMERA_TIMESTAMPS_CSV_ROW_DTYPE.names if not name.startswith(STAGE_PREFIXES)]
    assert header(recording.camera_timestamps_file_path_from_camera_id("cam0")) == base + [
        "frame.pre_frame_grab.ns", "frame.post_frame_grab.ns", "duration.during_frame_grab.ns"]

    multiframe_header = header(recording.timestamp_file_path)
    assert "duration.during_frame_grab.ms.median" in multiframe_header
    unstamped = ("initialized", "retrieve", "copy_to_camera_shm", "frame_record", "idle_before_frame_grab", "total.")
    assert [name for name in multiframe_header if any(event in name for event in unstamped)] == []

    report = Path(recording.timestamp_stats_text_file_path).read_text(encoding="utf-8")
    assert "During frame grab" in report
    for line in ("SHM", "retrieve", "frame record", "TOTAL"):
        assert line not in report
    stats = json.loads(Path(recording.timestamp_stats_json_file_path).read_text(encoding="utf-8"))
    assert "during_frame_grab_ms" in stats
    assert UNSTAMPED_STAGE_STATS.isdisjoint(stats)

    with open(recording.camera_timestamps_file_path_from_camera_id("cam1"), newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = [(int(frame.timestamps.pre_frame_grab_ns[0]) + int(frame.timestamps.post_frame_grab_ns[0])) // 2
                for frame in frames["cam1"]]
    assert [int(row["timestamp.perf_counter_ns.ns"]) for row in rows] == expected


RUST_ONLY_COLUMNS = ["frame.copied_from_driver.ns", "frame.sent_to_multiframe.ns", "frame.received_by_multiframe.ns",
                     "frame.pre_write_to_video_encoder.ns", "frame.post_write_to_video_encoder.ns"]


def test_rust_timing_file_becomes_the_standard_camera_timestamps_file(tmp_path: Path, monkeypatch):
    import skellycam.core.camera_group.rust_recording as rust_recording

    recording = RecordingInfo(recording_name="rec", recording_directory=str(tmp_path))
    configs = {"cam0": CameraConfig(camera_id="cam0", camera_index=0)}
    # The file Rust writes during recording (skellycam-rust timestamps/csv_writer.rs), at the standard path.
    csv_path = Path(recording.camera_timestamps_file_path_from_camera_id("cam0"))
    with open(csv_path, "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frame_number", "pre_frame_grab_ns", "post_frame_grab_ns", "copied_from_driver_ns",
                         "sent_to_multiframe_ns", "received_by_multiframe_ns", "pre_write_to_video_encoder_ns",
                         "post_write_to_video_encoder_ns"])
        writer.writerow([7, 100, 150, 160, 170, 400, 500, 510])
        writer.writerow([8, 33_000_100, 33_000_150, 33_000_160, 33_000_170, 33_000_400, 33_000_500, 33_000_510])
    captured = {}

    class CaptureFinalizer:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return CaptureFinalizer()

        async def finalize_recording(self):
            return "finalized"

    monkeypatch.setattr(rust_recording, "RecordingFinalizer", CaptureFinalizer)
    result = asyncio.run(rust_recording.finalize_rust_recording(
        summary={"csv_paths": [str(csv_path)]}, recording_info=recording, camera_configs=configs, timebase=MAPPING))

    assert result == "finalized"
    stamps = captured["frame_metadatas_by_camera"]["cam0"][0].timestamps
    assert (int(stamps.pre_frame_grab_ns[0]), int(stamps.post_frame_grab_ns[0])) == (100, 150)
    assert {name: int(stamps[name][0]) for name in stamps.dtype.names if name not in GRAB_BRACKET} == {
        name: 0 for name in stamps.dtype.names if name not in GRAB_BRACKET}

    # The shared finalizer rewrites that same file in the standard layout, keeping Rust's own events.
    asyncio.run(process_and_save_recording_timestamps(
        captured["frame_metadatas_by_camera"], configs, recording,
        additional_lifecycle_timestamps_by_camera=captured["additional_lifecycle_timestamps_by_camera"]))
    base = [name for name in CAMERA_TIMESTAMPS_CSV_ROW_DTYPE.names if not name.startswith(STAGE_PREFIXES)]
    assert header(csv_path) == base + ["frame.pre_frame_grab.ns", "frame.post_frame_grab.ns",
                                       "duration.during_frame_grab.ns"] + RUST_ONLY_COLUMNS
    with open(csv_path, newline="") as stream:
        first = next(csv.DictReader(stream))
    # Like every frame.*.ns column: nanoseconds after the recording's first frame-grab start (100).
    assert [int(first[column]) for column in RUST_ONLY_COLUMNS] == [60, 70, 300, 400, 410]
    assert int(first["timestamp.perf_counter_ns.ns"]) == 125
    assert not [path for path in tmp_path.rglob("*") if "native" in path.name]
