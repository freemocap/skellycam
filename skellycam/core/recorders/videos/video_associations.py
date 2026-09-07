"""Declared recording source-to-video associations, independent of filename conventions."""

from pathlib import Path, PureWindowsPath
from typing import Self

from pydantic import RootModel, model_validator


class VideoAssociations(RootModel[dict[str, str]]):
    @model_validator(mode="after")
    def validate_associations(self) -> Self:
        if not self.root:
            raise ValueError("Video associations must contain at least one source")
        for source, filename in self.root.items():
            if not source.strip() or source != source.strip():
                raise ValueError("Video source IDs must be nonempty and have no surrounding whitespace")
            windows_path = PureWindowsPath(filename)
            if (
                not filename.strip()
                or Path(filename).is_absolute()
                or windows_path.drive
                or windows_path.root
                or ".." in windows_path.parts
            ):
                raise ValueError(f"Video path must be relative to its video folder: {filename!r}")
        return self

    def resolve_paths(self, *, video_folder: Path) -> dict[str, Path]:
        folder = video_folder.resolve(strict=True)
        resolved: dict[str, Path] = {}
        owners: dict[Path, str] = {}
        for source, filename in self.root.items():
            path = (folder / filename).resolve(strict=True)
            if not path.is_relative_to(folder) or not path.is_file():
                raise ValueError(f"Source {source!r} must reference a video file inside {folder}: {path}")
            if path in owners:
                raise ValueError(f"Sources {owners[path]!r} and {source!r} reference the same video: {path}")
            owners[path] = source
            resolved[source] = path
        return resolved
