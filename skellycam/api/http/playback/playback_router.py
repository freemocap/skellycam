"""
Playback router: serves pre-recorded video files over HTTP for browser-native
<video> playback. Supports range requests for efficient seeking.

Workflow:
1. POST /playback/load  — point the server at a recording folder
2. GET  /playback/videos — list loaded videos with metadata
3. GET  /playback/video/{video_id} — stream a video file (range-request aware)
4. GET  /playback/recordings — list available recordings in the default directory
"""
import csv
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from skellycam.system.default_paths import get_default_skellycam_recordings_path

logger = logging.getLogger(__name__)

playback_router = APIRouter(prefix="/playback", tags=["Playback"])

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
TIMESTAMP_EXTENSIONS = {".csv"}

# ---------------------------------------------------------------------------
# Module-level state for the currently loaded recording
# ---------------------------------------------------------------------------

_loaded_videos: dict[str, Path] = {}
_loaded_recording_path: Path | None = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LoadRecordingRequest(BaseModel):
    recording_path: str = Field(description="Absolute path to a recording folder (or subfolder containing videos)")


class VideoInfo(BaseModel):
    video_id: str
    filename: str
    size_bytes: int
    stream_url: str


class LoadRecordingResponse(BaseModel):
    recording_path: str
    videos: list[VideoInfo]


class RecordingListEntry(BaseModel):
    name: str
    path: str
    video_count: int
    total_size_bytes: int = 0
    created_timestamp: Optional[str] = None
    total_frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _discover_videos(folder: Path) -> dict[str, Path]:
    """Find video files in a folder, keyed by a stable ID derived from the filename stem."""
    videos: dict[str, Path] = {}
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
            video_id = p.stem
            videos[video_id] = p
    return videos


def _find_video_folder(recording_path: Path) -> Path:
    """Resolve the actual folder containing video files.

    Accepts either:
    - A folder that directly contains .mp4 files
    - A recording root that has a synchronized_videos/ subfolder
    """
    if any(p.suffix.lower() in VIDEO_EXTENSIONS for p in recording_path.iterdir() if p.is_file()):
        return recording_path

    synced = recording_path / "synchronized_videos"
    if synced.is_dir():
        return synced

    raise FileNotFoundError(
        f"No video files found in {recording_path} or {recording_path}/synchronized_videos/"
    )


def _get_total_size(video_folder: Path) -> int:
    """Sum of all video file sizes in a folder."""
    total = 0
    for p in video_folder.iterdir():
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _get_recording_stats(recording_path: Path, video_folder: Path) -> dict:
    """Try to extract frame count, duration, and fps from timestamp CSV files."""
    stats: dict = {
        "total_frames": None,
        "duration_seconds": None,
        "fps": None,
    }

    # Look for timestamp CSV files in various locations
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

                    # Try to get timestamps for duration/fps calculation
                    # Look for a column that contains timestamp data
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

                            # If duration seems to be in nanoseconds or milliseconds, convert
                            if duration > 1e15:  # nanoseconds
                                duration /= 1e9
                            elif duration > 1e6:  # milliseconds
                                duration /= 1e3

                            if duration > 0:
                                stats["duration_seconds"] = round(duration, 2)
                                stats["fps"] = round(frame_count / duration, 1)
                        except (ValueError, IndexError):
                            pass

                    # Found a timestamp file — use it and stop
                    return stats
            except (OSError, csv.Error):
                continue

    return stats


def _get_created_timestamp(recording_path: Path) -> Optional[str]:
    """Try to determine the recording creation time from folder name or file metadata."""
    try:
        # Most reliable: folder creation / modification time
        stat = recording_path.stat()
        from datetime import datetime
        created = datetime.fromtimestamp(stat.st_mtime)
        return created.isoformat(timespec="seconds")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@playback_router.get("/recordings", summary="List available recordings in the default directory")
def list_recordings() -> list[RecordingListEntry]:
    recordings_dir = Path(get_default_skellycam_recordings_path())
    if not recordings_dir.is_dir():
        return []

    entries: list[RecordingListEntry] = []
    for child in sorted(recordings_dir.iterdir(), reverse=True):  # newest first by name
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


@playback_router.post("/load", summary="Load a recording folder for playback")
def load_recording(
    request_body: LoadRecordingRequest,
) -> LoadRecordingResponse:
    global _loaded_videos, _loaded_recording_path

    recording_path = Path(request_body.recording_path).expanduser().resolve()
    if not recording_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: {recording_path}")

    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    if not videos:
        raise HTTPException(status_code=404, detail=f"No video files found in {video_folder}")

    _loaded_videos = videos
    _loaded_recording_path = recording_path

    video_infos = [
        VideoInfo(
            video_id=vid_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            stream_url=f"/skellycam/playback/video/{vid_id}",
        )
        for vid_id, path in videos.items()
    ]

    logger.info(f"Loaded {len(videos)} videos from {recording_path}")
    return LoadRecordingResponse(
        recording_path=str(recording_path),
        videos=video_infos,
    )


@playback_router.get("/videos", summary="List currently loaded videos")
def list_loaded_videos() -> list[VideoInfo]:
    return [
        VideoInfo(
            video_id=vid_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            stream_url=f"/skellycam/playback/video/{vid_id}",
        )
        for vid_id, path in _loaded_videos.items()
    ]


@playback_router.get(
    "/video/{video_id}",
    summary="Stream a loaded video file (supports HTTP range requests for seeking)",
)
def stream_video(video_id: str) -> FileResponse:
    if video_id not in _loaded_videos:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not loaded. Call POST /playback/load first.")

    video_path = _loaded_videos[video_id]
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail=f"Video file no longer exists: {video_path}")

    suffix = video_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(video_path),
        media_type=media_type,
        filename=video_path.name,
    )


@playback_router.get(
    "/timestamps/{video_id}",
    summary="Get timestamp CSV data for a loaded video (if available)",
)
def get_timestamps(video_id: str) -> dict:
    if _loaded_recording_path is None:
        raise HTTPException(status_code=404, detail="No recording loaded")

    timestamp_dirs = [
        _loaded_recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        _loaded_recording_path / "synchronized_videos" / "timestamps",
        _loaded_recording_path / "timestamps",
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

    raise HTTPException(status_code=404, detail=f"No timestamp data found for video '{video_id}'")


@playback_router.get(
    "/timestamps",
    summary="Get per-frame timestamps (seconds from recording start) for all loaded cameras",
)
def get_all_timestamps() -> dict:
    """Return a mapping of video_id -> list of per-frame timestamps in seconds.

    Searches for camera timestamp CSVs produced by the recording finalizer and
    extracts the 'timestamp.from_recording_start.sec' column. Falls back to an
    empty dict if no timestamp data is found.
    """
    if _loaded_recording_path is None:
        raise HTTPException(status_code=404, detail="No recording loaded")

    timestamp_dirs = [
        _loaded_recording_path / "synchronized_videos" / "timestamps" / "camera_timestamps",
        _loaded_recording_path / "synchronized_videos" / "timestamps",
        _loaded_recording_path / "timestamps",
    ]

    result: dict[str, list[float]] = {}

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

                    # Find the 'from_recording_start' column
                    ts_col: int | None = None
                    for i, col_name in enumerate(header):
                        col_lower = col_name.strip().lower()
                        if "from_recording_start" in col_lower and "sec" in col_lower:
                            ts_col = i
                            break

                    if ts_col is None:
                        # Fall back: look for any timestamp/seconds column
                        for i, col_name in enumerate(header):
                            col_lower = col_name.strip().lower()
                            if any(kw in col_lower for kw in ["timestamp", "elapsed", "seconds"]):
                                ts_col = i
                                break

                    if ts_col is None:
                        continue

                    timestamps: list[float] = []
                    for row in reader:
                        try:
                            val = float(row[ts_col])
                            # Convert from ns/ms if needed
                            if val > 1e15:
                                val /= 1e9
                            elif val > 1e6:
                                val /= 1e3
                            timestamps.append(val)
                        except (ValueError, IndexError):
                            continue

                    if timestamps:
                        # Derive video_id: match against loaded videos by checking if
                        # any loaded video id appears in the filename
                        matched_id: str | None = None
                        for vid_id in _loaded_videos:
                            if vid_id in ts_file.stem:
                                matched_id = vid_id
                                break
                        if matched_id is None:
                            # Use the CSV stem as key
                            matched_id = ts_file.stem
                        result[matched_id] = timestamps
            except (OSError, csv.Error):
                continue

        # If we found anything in this directory, stop searching deeper
        if result:
            break

    return {"timestamps": result}


@playback_router.post(
    "/open-folder",
    summary="Open the currently loaded recording folder in the system file explorer",
)
def open_recording_folder() -> dict:
    """Open the loaded recording folder in the OS file explorer."""
    if _loaded_recording_path is None:
        raise HTTPException(status_code=400, detail="No recording loaded")

    import subprocess
    import sys

    folder = str(_loaded_recording_path)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {e}")

    return {"opened": folder}
