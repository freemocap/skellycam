"""
Playback router: serves pre-recorded video files over HTTP for browser-native
<video> playback. Supports range requests for efficient seeking.

Endpoints are keyed on {recording_id} (the recording folder name). The full
recording path is resolved as {BASE_RECORDINGS_DIRECTORY}/{recording_id},
with an optional `recording_parent_directory` query param to override the base.

Endpoints:
  GET  /playback/recordings                              — list available recordings
  GET  /playback/{recording_id}/videos                   — list videos in a recording
  GET  /playback/{recording_id}/videos/{video_id}        — stream a video file
"""
import logging
from skellycam.core.recorders.videos.recording_statistics import read_recording_statistics
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from skellycam.core.recorders.videos.video_associations import VideoAssociations
from skellycam.core.recorders.videos.video_file_metadata import probe_video_files
from skellycam.core.timestamps.recording_timing_reader import camera_timing_path, resolve_camera_timing
from skellycam.system.default_paths import get_default_skellycam_recordings_path

logger = logging.getLogger(__name__)

playback_router = APIRouter(prefix="/playback", tags=["Playback"])

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
TIMESTAMP_EXTENSIONS = {".csv"}


# ---------------------------------------------------------------------------
# Response models
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_recording_path(
    recording_id: str,
    recording_parent_directory: str | None = None,
) -> Path:
    """Resolve the full recording path from recording_id + optional parent dir.

    Raises HTTPException(404) if the directory does not exist.
    Raises HTTPException(400) for path traversal attempts.
    """
    parent = (
        Path(recording_parent_directory)
        if recording_parent_directory
        else Path(get_default_skellycam_recordings_path())
    )
    parent = parent.expanduser().resolve()
    recording_path = (parent / recording_id).resolve()

    # Path traversal guard
    if not str(recording_path).startswith(str(parent)):
        raise HTTPException(status_code=400, detail="Invalid recording_id")

    if not recording_path.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Recording directory not found: {recording_path}",
        )
    return recording_path


def _discover_videos(folder: Path) -> dict[str, Path]:
    """Find media by complete filename, including extension."""
    videos: dict[str, Path] = {}
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    for p in sorted(folder.iterdir()):
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in VIDEO_EXTENSIONS:
            video_id = p.name
            videos[video_id] = p
    return videos


def _find_video_folder(recording_path: Path) -> Path:
    """Resolve the actual folder containing video files.

    Looks for a synchronized_videos/ subfolder first, then falls back to
    videos directly in the recording root.
    """
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
    """Sum of all video file sizes in a folder."""
    total = 0
    for p in video_folder.iterdir():
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _get_recording_stats(recording_path: Path, video_folder: Path, *, use_cv2_fallback: bool = False) -> dict:
    return read_recording_statistics(recording_folder=recording_path, video_folder=video_folder,
                                     inspect_video=use_cv2_fallback)


def _get_created_timestamp(recording_path: Path) -> str | None:
    """Try to determine the recording creation time from folder name or file metadata."""
    try:
        stat = recording_path.stat()
        from datetime import datetime
        created = datetime.fromtimestamp(stat.st_mtime)
        return created.isoformat(timespec="seconds")
    except OSError:
        return None


@playback_router.get("/recordings", summary="List available recordings")
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


@playback_router.get(
    "/{recording_id}/videos",
    summary="List videos in a recording",
)
def list_videos(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> list[VideoInfo]:
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    videos = _discover_videos(video_folder)
    if not videos:
        raise HTTPException(status_code=404, detail=f"No video files found in {video_folder}")

    logger.info(f"Discovered {len(videos)} videos in recording '{recording_id}'")
    result = []
    for vid_id, path in videos.items():
        result.append(VideoInfo(
            video_id=vid_id,
            filename=path.name,
            size_bytes=path.stat().st_size,
            stream_url=f"/skellycam/playback/{recording_id}/videos/{vid_id}",
        ))
    return result


@playback_router.get(
    "/{recording_id}/videos/{video_id}",
    summary="Stream a video file (supports HTTP range requests for seeking)",
)
def stream_video(
    recording_id: str,
    video_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
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
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail=f"Video file no longer exists: {video_path}")

    serve_path = video_path

    suffix = serve_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(serve_path),
        media_type=media_type,
        content_disposition_type='inline',
        filename=serve_path.name,
    )


@playback_router.get(
    "/{recording_id}/timestamps",
    summary="Get timestamps for all videos in a recording",
)
def get_all_timestamps(
    recording_id: str,
    recording_parent_directory: str | None = Query(
        default=None,
        description="Override the default recordings directory",
    ),
) -> dict:
    """Return frame timestamps for every video in the recording.

    Response shape: {"timestamps": {"<video_id>": [t0, t1, ...], ...}, "warnings": [...]}
    Videos without discoverable timestamp CSVs produce a warning instead of an error.
    """
    recording_path = _resolve_recording_path(recording_id, recording_parent_directory)

    try:
        video_folder = _find_video_folder(recording_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    associations = VideoAssociations.from_recording_folder(recording_folder=recording_path)
    timestamps: dict[str, tuple[float, ...]] = {}
    for path, metadata in probe_video_files(paths=_discover_videos(video_folder).values()).items():
        source = associations.source_for_path(video_folder=video_folder, video_path=path) if associations else None
        values = tuple(frame / metadata.reported_fps for frame in range(metadata.reported_frame_count))
        if source is not None:
            values = resolve_camera_timing(path=camera_timing_path(recording_folder=recording_path, camera_id=source),
                frame_count=metadata.reported_frame_count, fps=metadata.reported_fps, offset_s=0.0).timestamps_s
        timestamps[path.name] = values
    return {"timestamps": timestamps, "warnings": []}
