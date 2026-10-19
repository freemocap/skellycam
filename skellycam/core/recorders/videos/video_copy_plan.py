"""Validate a complete media copy operation before creating destination files."""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from shutil import copyfileobj, copystat


@dataclass(frozen=True, slots=True)
class VideoCopyPlan:
    sources: tuple[Path, ...]
    destinations: tuple[Path, ...]

    @classmethod
    def create(cls, *, source_files: tuple[Path, ...], destination_folder: Path,
               destination_names: tuple[str, ...]) -> "VideoCopyPlan":
        if not source_files or len(source_files) != len(destination_names):
            raise ValueError("Every selected video must have exactly one destination")
        sources = tuple(path.expanduser().resolve(strict=True) for path in source_files)
        if any(not path.is_file() for path in sources):
            raise ValueError("Every selected video must be a file")
        if len(set(sources)) != len(sources):
            raise ValueError("The same video was selected more than once")
        for name in destination_names:
            if not name or PureWindowsPath(name).name != name or name in {".", ".."}:
                raise ValueError(f"Invalid destination filename: {name!r}")
        if len({name.casefold() for name in destination_names}) != len(destination_names):
            raise ValueError("Selected videos have colliding destination filenames")
        destinations = tuple(destination_folder / name for name in destination_names)
        for path in destinations:
            if path.exists():
                raise FileExistsError(f"Import would overwrite an existing file: {path}")
        return cls(sources=sources, destinations=destinations)

    def copy_files(self) -> None:
        for source, destination in zip(self.sources, self.destinations, strict=True):
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as source_file, destination.open("xb") as destination_file:
                copyfileobj(source_file, destination_file)
            copystat(source, destination)
