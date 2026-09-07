"""Read declared file relationships independently from recording metadata."""

import json
from enum import StrEnum
from pathlib import Path, PureWindowsPath


class RecordingFileField(StrEnum):
    VIDEOS = "videos"
    CAMERA_TIMING = "camera_timing"
    MULTIFRAME_TIMING = "multiframe_timing"


def read_recording_field(*, recording_folder: Path, field: RecordingFileField) -> object | None:
    declared: object | None = None
    for path in sorted(recording_folder.glob("*_info.json")):
        with path.open(encoding="utf-8") as stream:
            metadata = json.load(stream)
        if not isinstance(metadata, dict):
            raise ValueError(f"Recording metadata must be an object: {path}")
        if field not in metadata:
            continue
        value = metadata[field]
        if value is None:
            raise ValueError(f"Recording field {field} must not be null: {path}")
        if declared is not None and declared != value:
            raise ValueError(f"Conflicting {field} associations in recording metadata: {recording_folder}")
        declared = value
    return declared


def resolve_recording_file(*, recording_folder: Path, relative_path: str) -> Path:
    path = PureWindowsPath(relative_path)
    if not relative_path or path.drive or path.root or ".." in path.parts:
        raise ValueError(f"Expected a recording-relative path: {relative_path!r}")
    folder = recording_folder.resolve()
    resolved = (folder / relative_path).resolve()
    if not resolved.is_relative_to(folder):
        raise ValueError(f"Recording file escapes recording folder: {resolved}")
    return resolved
