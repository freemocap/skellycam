"""Declared recording source-to-video associations, independent of filename conventions."""

from pathlib import Path
from typing import Self

from pydantic import RootModel, model_validator
from skellycam.core.recorders.videos.recording_metadata import (
    RecordingFileField, read_recording_field, resolve_recording_file, validate_recording_relative_path,
)


class VideoAssociations(RootModel[dict[str, str]]):
    @classmethod
    def from_recording_folder(cls, *, recording_folder: Path) -> "VideoAssociations | None":
        value = read_recording_field(recording_folder=recording_folder, field=RecordingFileField.VIDEOS)
        return cls.model_validate(value, strict=True) if value is not None else None

    def source_for_path(self, *, video_folder: Path, video_path: Path) -> str | None:
        target = video_path.resolve()
        matches = [source for source, filename in self.root.items()
                   if resolve_recording_file(recording_folder=video_folder, relative_path=filename) == target]
        if len(matches) > 1:
            raise ValueError(f"Multiple sources reference video {video_path}")
        return matches[0] if matches else None

    @model_validator(mode="after")
    def validate_associations(self) -> Self:
        if not self.root:
            raise ValueError("Video associations must contain at least one source")
        for source, filename in self.root.items():
            if not source.strip() or source != source.strip():
                raise ValueError("Video source IDs must be nonempty and have no surrounding whitespace")
            self.root[source] = validate_recording_relative_path(relative_path=filename)
        return self

    def resolve_paths(self, *, video_folder: Path) -> dict[str, Path]:
        folder = video_folder.resolve(strict=True)
        resolved: dict[str, Path] = {}
        owners: dict[Path, str] = {}
        for source, filename in self.root.items():
            path = resolve_recording_file(recording_folder=folder, relative_path=filename).resolve(strict=True)
            if not path.is_relative_to(folder) or not path.is_file():
                raise ValueError(f"Source {source!r} must reference a video file inside {folder}: {path}")
            if path in owners:
                raise ValueError(f"Sources {owners[path]!r} and {source!r} reference the same video: {path}")
            owners[path] = source
            resolved[source] = path
        return resolved
