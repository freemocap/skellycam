"""Video file properties, independent of capture-device identity and recording layout."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import cv2


@dataclass(frozen=True, slots=True)
class VideoFileMetadata:
    file_path: Path
    width: int
    height: int
    reported_fps: float
    reported_frame_count: int
    fourcc: str

    @classmethod
    def from_path(cls, *, path: Path) -> "VideoFileMetadata":
        resolved = path.resolve(strict=True)
        capture = cv2.VideoCapture(str(resolved))
        try:
            if not capture.isOpened():
                raise ValueError(f"Cannot open video: {resolved}")
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = capture.get(cv2.CAP_PROP_FPS)
            frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid video dimensions: {resolved}")
            if not isfinite(fps) or fps <= 0:
                raise ValueError(f"Invalid reported video FPS: {resolved}")
            if not isfinite(frame_count) or frame_count < 1 or not frame_count.is_integer():
                raise ValueError(f"Invalid reported video frame count: {resolved}")
            fourcc_code = int(capture.get(cv2.CAP_PROP_FOURCC))
            return cls(file_path=resolved, width=width, height=height,
                reported_fps=fps, reported_frame_count=int(frame_count),
                fourcc="".join(chr((fourcc_code >> (8 * index)) & 0xFF) for index in range(4)))
        finally:
            capture.release()


def probe_video_files(*, paths: Iterable[Path]) -> dict[Path, VideoFileMetadata]:
    """Inspect each distinct absolute path once; reported counts are not decoded-frame validation."""
    result: dict[Path, VideoFileMetadata] = {}
    for path in paths:
        resolved = path.resolve(strict=True)
        if resolved not in result:
            result[resolved] = VideoFileMetadata.from_path(path=resolved)
    return result
