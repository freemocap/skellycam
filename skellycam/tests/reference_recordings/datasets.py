"""Standalone raw-video acquisition; no FreeMoCap or other subskelly imports."""

from dataclasses import dataclass
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile


@dataclass(frozen=True)
class Dataset:
    name: str
    url: str
    frames: int


TEST = Dataset("freemocap_test_data", "https://github.com/freemocap/skellysamples/releases/download/test_data_v06_09_25/freemocap_test_data.zip", 222)
SAMPLE = Dataset("freemocap_sample_data", "https://github.com/freemocap/skellysamples/releases/download/sample_data_v06_12_25/freemocap_sample_data.zip", 1108)


def video_paths(recording: Path) -> tuple[Path, ...]:
    folders = [folder for folder in (recording / "synchronized_videos", recording / "videos" / "synchronized")
               if folder.is_dir() and any(folder.glob("*.mp4"))]
    if len(folders) != 1:
        raise ValueError(f"Expected one synchronized video folder: {recording}; existing data was preserved")
    paths = tuple(sorted(folders[0].glob("*.mp4")))
    if len(paths) != 3 or any(not path.is_file() or path.stat().st_size == 0 for path in paths):
        raise ValueError(f"Expected three nonempty reference videos: {recording}")
    return paths


def acquire(dataset: Dataset, *, recordings_root: Path | None = None) -> tuple[Path, ...]:
    if dataset not in (TEST, SAMPLE):
        raise ValueError("Unknown reference dataset")
    root = (recordings_root or Path.home() / "freemocap_data" / "recordings").expanduser().resolve()
    destination = root / dataset.name
    if destination.exists():
        return video_paths(destination)
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{dataset.name}-", dir=root) as temporary:
        staging = Path(temporary)
        archive_path = staging / "download.zip"
        with urlopen(dataset.url, timeout=300) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        extracted = staging / "extracted"
        extracted.mkdir()
        with ZipFile(archive_path) as archive:
            for member in archive.infolist():
                name = member.filename.replace("\\", "/")
                if ":" in name or not (extracted / name).resolve().is_relative_to(extracted):
                    raise ValueError(f"Unsafe archive member: {name}")
            archive.extractall(extracted)
        candidates = {folder.parent for folder in extracted.rglob("synchronized_videos") if folder.is_dir()}
        candidates.update(folder.parent.parent for folder in extracted.rglob("synchronized")
                          if folder.is_dir() and folder.parent.name == "videos")
        if len(candidates) != 1:
            raise ValueError("Archive must contain exactly one recording")
        recording = candidates.pop()
        video_paths(recording)
        # A concurrently completed download wins; never overwrite its recording.
        if destination.exists():
            return video_paths(destination)
        try:
            recording.rename(destination)
        except OSError:
            if not destination.exists():
                raise
            return video_paths(destination)
    return video_paths(destination)
