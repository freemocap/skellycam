import logging
import re
from dataclasses import dataclass
from pathlib import Path

from tabulate import tabulate

from skellycam.core.camera.config.camera_config import CameraConfig

logger = logging.getLogger(__name__)

VIDEO_STEM_FORMAT = "{recording_name}.id-{camera_id}.idx-{camera_index}"
VIDEO_FILENAME_RE = re.compile(
    r"^(?P<recording_name>.+)\.id-(?P<camera_id>[^.]+)\.idx-(?P<camera_index>\d+)$"
)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

_CAMERA_NUM_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}

_WORD_ALTERNATION = "|".join(sorted(_CAMERA_NUM_WORDS.keys(), key=len, reverse=True))

# Matches: camera0, cam0, camera_0, cam-1, camera two, cam_three, cam_nineteen, etc.
_CAM_PREFIX_RE = re.compile(
    rf"(?:camera|cam)[_.\- ]?(?P<num>\d+|{_WORD_ALTERNATION})",
    re.IGNORECASE,
)

# Matches embedded small integers (≤ 2 digits): video_0, clip-1, etc.
_TRAILING_INT_RE = re.compile(r"(?:^|[_.\- ])(\d{1,2})(?:[_.\- ]|$)")


def try_extract_camera_info(stem: str) -> tuple[str | None, int | None, str]:
    """Try to extract camera_id and camera_index from a non-canonical filename stem.

    Returns (camera_id, camera_index, source_label).
    source_label is one of: "cam-prefix", "trailing-int", "opaque".
    camera_id and/or camera_index may be None if not determinable.
    """
    m = _CAM_PREFIX_RE.search(stem)
    if m:
        raw = m.group("num")
        idx = int(raw) if raw.isdigit() else _CAMERA_NUM_WORDS[raw.lower()]
        return m.group(0), idx, "cam-prefix"

    m2 = _TRAILING_INT_RE.search(stem)
    if m2:
        idx = int(m2.group(1))
        if idx <= 20:
            return str(idx), idx, "trailing-int"

    return None, None, "opaque"




@dataclass
class ParsedVideoFilename:
    recording_name: str
    camera_id: str
    camera_index: int
    extension: str  # without leading dot, e.g. "mp4"

    @property
    def stem(self) -> str:
        return VIDEO_STEM_FORMAT.format(
            recording_name=self.recording_name,
            camera_id=self.camera_id,
            camera_index=self.camera_index,
        )

    @property
    def filename(self) -> str:
        return f"{self.stem}.{self.extension}"

    @classmethod
    def from_camera_config(cls, recording_name: str, config: "CameraConfig", extension: str) -> "ParsedVideoFilename":
        """Build a ParsedVideoFilename from a recording name and camera config (forward direction)."""
        return cls(
            recording_name=recording_name,
            camera_id=config.camera_id,
            camera_index=config.camera_index,
            extension=extension.lstrip("."),
        )

    @classmethod
    def from_path(cls, video_path: str | Path) -> "ParsedVideoFilename":
        """Parse a video file path to its components.

        Tries the canonical SkellyCam pattern first. If the filename does not match,
        logs a warning and returns a best-guess result using progressive fallback
        heuristics rather than raising an exception.

        Fallback precedence:
          1. cam-prefix  — "camera0", "cam_three", "cam-two", etc.
          2. trailing-int — small integer embedded in stem (≤ 20)
          3. opaque       — full stem used as camera_id; index set to -1 (sentinel)
        """
        p = Path(video_path)
        match = VIDEO_FILENAME_RE.match(p.stem)
        if match:
            return cls(
                recording_name=match.group("recording_name"),
                camera_id=match.group("camera_id"),
                camera_index=int(match.group("camera_index")),
                extension=p.suffix.lstrip("."),
            )

        # Non-canonical — apply heuristics
        cam_id, cam_index, source = try_extract_camera_info(p.stem)

        if cam_id is None:
            cam_id = p.stem

        if cam_index is None and cam_id.isdigit() and int(cam_id) <= 20:
            cam_index = int(cam_id)
            source = "trailing-int"

        if cam_index is None:
            cam_index = -1  # sentinel: to be resolved by parse_video_folder

        recording_name = p.parent.name or p.stem

        logger.warning(
            f"Filename '{p.name}' does not match canonical SkellyCam pattern "
            f"'<recording_name>.id-<camera_id>.idx-<camera_index>.<ext>'. "
            f"Best-guess ({source}): camera_id={cam_id!r}, camera_index={cam_index}"
        )

        return cls(
            recording_name=recording_name,
            camera_id=cam_id,
            camera_index=cam_index,
            extension=p.suffix.lstrip("."),
        )


def parse_video_folder(
    source: Path | list[Path | str],
) -> list[ParsedVideoFilename]:
    """Parse all video files in a folder or list of paths.

    Uses from_path() with fallback heuristics for each file. If any camera indices
    are unknown (sentinel -1) or collide across files, all indices are re-assigned
    by alphabetical filename order. Emits a debug table summarising the final
    assignments via logger.debug.
    """
    if isinstance(source, Path):
        paths: list[Path] = sorted(
            p for p in source.glob("*")
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        )
    else:
        paths = sorted(Path(p) for p in source)

    if not paths:
        logger.warning(f"parse_video_folder: no video files found in {source!r}")
        return []

    results: list[ParsedVideoFilename] = []
    parse_sources: list[str] = []

    for p in paths:
        if VIDEO_FILENAME_RE.match(p.stem):
            parse_sources.append("canonical")
        else:
            _, _, src = try_extract_camera_info(p.stem)
            parse_sources.append(src)
        results.append(ParsedVideoFilename.from_path(p))

    # Detect index collisions or unknowns and re-assign if needed
    indices = [r.camera_index for r in results]
    needs_reindex = (-1 in indices) or (len(set(indices)) < len(indices))

    if needs_reindex:
        logger.warning(
            f"parse_video_folder: camera indices are ambiguous or colliding "
            f"({indices}); re-assigning by alphabetical filename order."
        )
        for i, r in enumerate(results):
            r.camera_index = i
        parse_sources = [
            "alphabetical fallback" if s == "opaque" else s
            for s in parse_sources
        ]

    table_rows = [
        [paths[i].name, results[i].camera_id, results[i].camera_index, parse_sources[i]]
        for i in range(len(results))
    ]
    logger.debug(
        "parse_video_folder results:\n"
        + tabulate(
            table_rows,
            headers=["filename", "camera_id", "camera_index", "source"],
            tablefmt="simple",
        )
    )

    return sorted(results, key=lambda r: r.camera_index)
