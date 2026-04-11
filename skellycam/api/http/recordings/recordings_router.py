"""
Recordings resource endpoints.

GET    /recordings                                              — list available recordings
GET    /recordings/{recording_id}                               — recording detail (metadata + videos)
GET    /recordings/{recording_id}/videos                        — list videos in a recording
GET    /recordings/{recording_id}/videos/{video_id}             — stream a video file
GET    /recordings/{recording_id}/timestamps                    — timestamps for all videos
GET    /recordings/{recording_id}/videos/{video_id}/timestamps  — timestamps for one video
"""
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from skellycam.system.default_paths import get_default_skellycam_recordings_path

logger = logging.getLogger(__name__)

recordings_router = APIRouter(prefix="/recordings", tags=["Recordings"])

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class VideoInfo(BaseModel):
    video_id: str
    filename: str
    size_bytes: int
    stream_url: str


class RecordingListEntry(BaseModel):
    name: str
    path: str
    video_count: int
    total_size_bytes: int = 0
    created_timestamp: Optional[str] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None


class StatsSummary(BaseModel):
    median: float
    mean: float
    std: float
    min: float
    max: float


class StopRecordingResponse(BaseModel):
    recording_name: str
    recording_path: str
    number_of_cameras: int
    number_of_frames: int
    total_duration_sec: float
    mean_framerate: float
    mean_inter_camera_sync_ms: float
    framerate_stats: StatsSummary
    frame_duration_stats: StatsSummary
    inter_camera_grab_range_ms_stats: StatsSummary


class RecordingDetailResponse(BaseModel):
    """Response for GET /recordings/{recording_id}."""
    name: str
    path: str
    video_count: int
    total_size_bytes: int = 0
    created_timestamp: Optional[str] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    videos: list[VideoInfo] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_recording_path(
        recording_id: str,
        recording_parent_directory: str | None = None,
) -> Path:
    parent = (
        Path(recording_parent_directory)
        if recording_parent_directory
        else Path(get_default_skellycam_recordings_path())
    )
    parent = parent.expanduser().resolve()
    recording_path = (parent / recording_id).resolve()

    if not str(recording_path).startswith(str(parent)):
        raise HTTPException(status_code=400, detail="Invalid recording_id")

    if not recording_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Recording directory not found: {recording_path}",
        )
    return recording_path


def _discover_videos(folder: Path) -> dict[str, Path]:
    videos: dict[str, Path] = {}
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
            videos[p.stem] = p
    return videos


def _find_video_folder(recording_path: Path) -> Path:
    synced = recording_path / "synchronized_videos"
    if synced.is_dir():
        if any(p.suffix.lower() in VIDEO_EXTENSIONS for p in synced.iterdir() if p.is_file()):
            return synced
    if any(p.suffix.lower() in VIDEO_EXTENSIONS for p in recording_path.iterdir() if p.is_file()):
        return recording_path
    raise FileNotFoundError(
        f"No video files found in {recording_path} or {recording_path}/synchronized_videos/"
    )


def _get_total_size(video_folder: Path) -> int:
    total = 0
    for p in video_folder.iterdir():
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _get_recording_stats(recording_path: Path, video_folder: Path) -> dict:
    stats: dict = {"total_frames": None, "duration_seconds": None, "fps": None}
    timestamp_dirs = [
        recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        recording_path / "synchronized_videos" / "timestamps",
        recording_path / "timestamps",
        video_folder,
    ]
    for ts_dir in timestamp_dirs:
        if not ts_dir.is_dir():
            continue
        for ts_file in sorted(ts_dir.iterdir()):
            if ts_file.suffix.lower() != ".csv":
                continue
            try:
                with open(ts_file, "r", newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header is None:
                        continue
                    rows = list(reader)
                    if len(rows) < 2:
                        continue
                    frame_count = len(rows)
                    stats["total_frames"] = frame_count
                    timestamp_col = None
                    for i, col_name in enumerate(header):
                        col_lower = col_name.strip().lower()
                        if any(kw in col_lower for kw in ["timestamp", "time", "elapsed", "seconds"]):
                            timestamp_col = i
                            break
                    if timestamp_col is not None and len(rows) >= 2:
                        try:
                            first_ts = float(rows[0][timestamp_col])
                            last_ts = float(rows[-1][timestamp_col])
                            duration = abs(last_ts - first_ts)
                            if duration > 1e15:
                                duration /= 1e9
                            elif duration > 1e6:
                                duration /= 1e3
                            if duration > 0:
                                stats["duration_seconds"] = round(duration, 2)
                                stats["fps"] = round(frame_count / duration, 1)
                        except (ValueError, IndexError):
                            pass
                    return stats
            except (OSError, csv.Error):
                continue
    return stats


def _get_created_timestamp(recording_path: Path) -> str | None:
    try:
        stat = recording_path.stat()
        created = datetime.fromtimestamp(stat.st_mtime)
        return created.isoformat(timespec="seconds")
    except OSError:
        return None


def _read_timestamp_values_for_video(recording_path: Path, video_id: str) -> list[float] | None:
    timestamp_dirs = [
        recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        recording_path / "synchronized_videos" / "timestamps",
        recording_path / "timestamps",
    ]
    for ts_dir in timestamp_dirs:
        if not ts_dir.is_dir():
            continue
        for ts_file in ts_dir.iterdir():
            if ts_file.suffix.lower() != ".csv" or video_id not in ts_file.stem:
                continue
            try:
                with open(ts_file, "r", newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header is None:
                        continue
                    rows = list(reader)
                    if len(rows) < 2:
                        continue
                    timestamp_col: int | None = None
                    for i, col_name in enumerate(header):
                        col_lower = col_name.strip().lower()
                        if any(kw in col_lower for kw in ["timestamp", "time", "elapsed", "seconds"]):
                            timestamp_col = i
                            break
                    if timestamp_col is None:
                        continue
                    return [float(row[timestamp_col]) for row in rows]
            except (OSError, csv.Error, ValueError, IndexError):
                continue
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@recordings_router.get("", summary="List available recordings")
def list_recordings(
        recording_parent_directory: str | None = Query(
            default=None,
            description="Override the default recordings directory",
        ),
) -> list[RecordingListEntry]:
    recordings_dir = (
        Path(recording_parent_directory).expanduser().resolve()
        if recording_parent_directory
        else Path(get_default_skellycam_recordings_path())
    )
    if not recordings_dir.is_dir():
        return []

    entries: list[RecordingListEntry] = []
    for child in sorted(recordings_dir.iterdir(), reverse=True):
        if not child.is_dir():
            continue
        try:
            video_folder = _find_video_folder(child)
            video_count = sum(
                1 for p in video_folder.iterdir()
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
            )
            if video_count > 0:
                total_size = _get_total_size(video_folder)
                created_ts = _get_created_timestamp(child)
                stats = _get_recording_stats(child, video_folder)
                entries.append(RecordingListEntry(
                    name=child.name,
                    path=str(child),
                    video_count=video_count,
                    total_size_bytes=total_size,
                    created_timestamp=created_ts,
                    total_frames=stats.get("total_frames"),
                    duration_seconds=stats.get("duration_seconds"),
                    fps=stats.get("fps"),
                ))
        except (FileNotFoundError, PermissionError):
            continue
    return entries


@recordings_router.get(
    "/{recording_id}",
    summary="Get recording detail (metadata + video list)",
    response_model=RecordingDetailResponse,
)
def get_recording(
        recording_id: str,
        recording_parent_directory: str | None = Query(default=None),
) -> RecordingDetailResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    total_size = _get_total_size(video_folder)
    created_ts = _get_created_timestamp(recording_path)
    stats = _get_recording_stats(recording_path, video_folder)

    video_infos = [
        VideoInfo(
            video_id=vid_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            stream_url=f"/recordings/{recording_id}/videos/{vid_id}",
        )
        for vid_id, path in videos.items()
    ]

    return RecordingDetailResponse(
        name=recording_id,
        path=str(recording_path),
        video_count=len(videos),
        total_size_bytes=total_size,
        created_timestamp=created_ts,
        total_frames=stats.get("total_frames"),
        duration_seconds=stats.get("duration_seconds"),
        fps=stats.get("fps"),
        videos=video_infos,
    )


@recordings_router.get("/{recording_id}/videos", summary="List videos in a recording")
def list_videos(
        recording_id: str,
        recording_parent_directory: str | None = Query(default=None),
) -> list[VideoInfo]:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    if not videos:
        raise HTTPException(status_code=404, detail=f"No video files found in {video_folder}")

    return [
        VideoInfo(
            video_id=vid_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            stream_url=f"/recordings/{recording_id}/videos/{vid_id}",
        )
        for vid_id, path in videos.items()
    ]


@recordings_router.get(
    "/{recording_id}/videos/{video_id}",
    summary="Stream a video file (supports HTTP range requests)",
)
def stream_video(
        recording_id: str,
        video_id: str,
        recording_parent_directory: str | None = Query(default=None),
) -> FileResponse:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    if video_id not in videos:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found in recording '{recording_id}'")

    video_path = videos[video_id]
    suffix = video_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    return FileResponse(
        path=str(video_path),
        media_type=media_types.get(suffix, "application/octet-stream"),
        filename=video_path.name,
    )


@recordings_router.get(
    "/{recording_id}/timestamps",
    summary="Get timestamps for all videos in a recording",
)
def get_all_timestamps(
        recording_id: str,
        recording_parent_directory: str | None = Query(default=None),
) -> dict:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    all_timestamps: dict[str, list[float]] = {}
    warnings: list[str] = []

    for vid_id in videos:
        ts_values = _read_timestamp_values_for_video(recording_path, video_id=vid_id)
        if ts_values is not None:
            all_timestamps[vid_id] = ts_values
        else:
            warnings.append(f"No timestamp data found for video '{vid_id}'")

    return {"timestamps": all_timestamps, "warnings": warnings}


@recordings_router.get(
    "/{recording_id}/videos/{video_id}/timestamps",
    summary="Get timestamp data for a specific video",
)
def get_video_timestamps(
        recording_id: str,
        video_id: str,
        recording_parent_directory: str | None = Query(default=None),
) -> dict:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)
    timestamp_dirs = [
        recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        recording_path / "synchronized_videos" / "timestamps",
        recording_path / "timestamps",
    ]
    for ts_dir in timestamp_dirs:
        if not ts_dir.is_dir():
            continue
        for ts_file in ts_dir.iterdir():
            if ts_file.suffix.lower() == ".csv" and video_id in ts_file.stem:
                lines = ts_file.read_text().strip().split("\n")
                if len(lines) < 2:
                    continue
                headers = lines[0].split(",")
                rows = [line.split(",") for line in lines[1:]]
                return {
                    "video_id": video_id,
                    "headers": headers,
                    "row_count": len(rows),
                    "file": ts_file.name,
                }
    return {
        "video_id": video_id,
        "warning": f"No timestamp data found for video '{video_id}'",
        "headers": [],
        "row_count": 0,
    }
