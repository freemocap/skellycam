"""Read finalized capture timing in the recording's shared clock."""

import csv
from dataclasses import dataclass
import math
from pathlib import Path
from enum import StrEnum
from skellycam.system.default_paths import CAMERA_TIMESTAMPS_FOLDER_NAME


def camera_timing_path(*, recording_folder: Path, camera_id: str) -> Path:
    """Resolve a camera sidecar without creating directories during playback."""
    return recording_folder / CAMERA_TIMESTAMPS_FOLDER_NAME / f"{recording_folder.name}.camera{camera_id}.timestamps.csv"


class TimingMethod(StrEnum):
    RECORDED = "recorded"
    INFERRED_FROM_FPS = "inferred_from_fps"
    MEAN_CAMERA_TIMES = "mean_camera_times"


class TimingFileKind(StrEnum):
    CAMERA = "camera"
    MULTIFRAME = "multiframe"


@dataclass(frozen=True, slots=True)
class RecordingTiming:
    timestamps_s: tuple[float, ...]
    method: TimingMethod


def resolve_camera_timing(
    *,
    path: Path,
    frame_count: int,
    fps: float,
    offset_s: float,
) -> RecordingTiming:
    """Prefer recorded timing; absent sidecars use nominal FPS and the supplied offset."""
    if frame_count < 1 or not math.isfinite(offset_s):
        raise ValueError("Positive frame_count and finite offset_s are required")
    if path.exists():
        recorded = read_recording_timing(path=path, kind=TimingFileKind.CAMERA)
        if tuple(recorded) != tuple(range(frame_count)):
            raise ValueError(
                f"Camera timing does not cover the video frame grid: {path}"
            )
        return RecordingTiming(
            timestamps_s=tuple(recorded.values()), method=TimingMethod.RECORDED
        )
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("A finite positive FPS is required to infer missing timing")
    return RecordingTiming(
        timestamps_s=tuple(offset_s + frame / fps for frame in range(frame_count)),
        method=TimingMethod.INFERRED_FROM_FPS,
    )


def read_recording_timing(
    *,
    path: Path,
    kind: TimingFileKind,
) -> dict[int, float]:
    """Return recording-local frame indices and seconds without rebasing camera clocks."""
    frame_column = (
        "recording_frame_number"
        if kind == TimingFileKind.CAMERA
        else "multiframe_number"
    )
    time_column = "timestamp.from_recording_start.sec"
    result: dict[int, float] = {}
    last_frame = -1
    last_time = -math.inf
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"Empty timing file: {path}")
        reader.fieldnames = [name.removeprefix("# ") for name in reader.fieldnames]
        if not {frame_column, time_column}.issubset(reader.fieldnames):
            raise ValueError(f"Missing recording timing columns: {path}")
        for row in reader:
            frame = int(row[frame_column])
            timestamp = float(row[time_column])
            if (
                frame <= last_frame
                or not math.isfinite(timestamp)
                or timestamp <= last_time
            ):
                raise ValueError(
                    f"Invalid or unordered recording timing in {path}: {row}"
                )
            result[frame] = timestamp
            last_frame, last_time = frame, timestamp
    if not result:
        raise ValueError(f"No timing samples: {path}")
    return result
