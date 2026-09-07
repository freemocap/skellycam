"""Recording summaries from declared multiframe timing or inspected media."""

from pathlib import Path

from skellycam.core.recorders.videos.video_file_metadata import VideoFileMetadata
from skellycam.core.recorders.videos.video_filename import VIDEO_EXTENSIONS
from skellycam.core.timestamps.recording_timing_reader import read_recording_timing, TimingFileKind


def read_recording_statistics(*, recording_folder: Path, video_folder: Path,
                              inspect_video: bool) -> dict[str, int | float | None]:
    result: dict[str, int | float | None] = {"total_frames": None, "duration_seconds": None, "fps": None}
    timing_path = recording_folder / "timestamps" / f"{recording_folder.name}_timestamps.csv"
    if timing_path.is_file():
        timing = read_recording_timing(path=timing_path, kind=TimingFileKind.MULTIFRAME)
        result["total_frames"] = len(timing)
        values = list(timing.values())
        if len(values) > 1:
            duration = values[-1] - values[0]
            if duration > 0:
                result["duration_seconds"] = duration
                result["fps"] = (len(values) - 1) / duration
        return result
    if inspect_video:
        paths = sorted(path for path in video_folder.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)
        if paths:
            metadata = VideoFileMetadata.from_path(path=paths[0])
            result.update(total_frames=metadata.reported_frame_count, fps=metadata.reported_fps,
                          duration_seconds=metadata.reported_frame_count / metadata.reported_fps)
    return result
