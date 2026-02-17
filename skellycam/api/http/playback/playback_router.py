"""
Playback router: serves pre-recorded video files over HTTP for browser-native
<video> playback. Supports range requests for efficient seeking.

Workflow:
1. POST /playback/load  — point the server at a recording folder
2. GET  /playback/videos — list loaded videos with metadata
3. GET  /playback/video/{video_id} — stream a video file (range-request aware)
4. GET  /playback/recordings — list available recordings in the default directory
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@playback_router.get("/recordings", summary="List available recordings in the default directory")
def list_recordings() -> list[RecordingListEntry]:
    recordings_dir = Path(get_default_skellycam_recordings_path())
    if not recordings_dir.is_dir():
        return []

    entries: list[RecordingListEntry] = []
    for child in sorted(recordings_dir.iterdir()):
        if not child.is_dir():
            continue
        try:
            video_folder = _find_video_folder(child)
            video_count = sum(
                1 for p in video_folder.iterdir()
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
            )
            if video_count > 0:
                entries.append(RecordingListEntry(
                    name=child.name,
                    path=str(child),
                    video_count=video_count,
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

    # Determine media type from extension
    suffix = video_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    # FileResponse handles range requests automatically
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

    # Search for timestamp files in the expected locations
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
