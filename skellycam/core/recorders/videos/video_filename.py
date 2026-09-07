"""Generate capture filenames from explicit recording and camera configuration."""

from dataclasses import dataclass
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types.type_overloads import CameraIdString, CameraIndexInt

VIDEO_STEM_FORMAT = "{recording_name}.id-{camera_id}.idx-{camera_index}"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@dataclass
class VideoFilename:
    recording_name: str
    camera_id: CameraIdString
    camera_index: CameraIndexInt
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
    def from_camera_config(cls, recording_name: str, config: "CameraConfig", extension: str) -> "VideoFilename":
        """Build a VideoFilename from a recording name and camera config (forward direction)."""
        return cls(
            recording_name=recording_name,
            camera_id=config.camera_id,
            camera_index=config.camera_index,
            extension=extension.lstrip("."),
        )

