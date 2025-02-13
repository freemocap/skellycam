from pathlib import Path
from typing import Dict

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig


class VideoConfig(CameraConfig):
    video_path: Path
    exposure_mode: str = ""

VideoConfigs = Dict[CameraId, VideoConfig]