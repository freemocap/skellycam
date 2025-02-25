from pathlib import Path
from typing import Dict

import cv2
import logging
import sys

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig

from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.utilities.get_video_paths import get_video_paths

logger = logging.getLogger(__name__)


class VideoConfig(CameraConfig):
    video_path: Path
    num_frames: int
    exposure_mode: str = ""

VideoConfigs = Dict[int, VideoConfig]  # TODO: making this CameraID causes a circular import


def load_video_configs_from_folder(synchronized_video_folder_path: str | Path) -> VideoConfigs:
    logger.info(f"Loading video configs from folder: {synchronized_video_folder_path}")
    video_configs = {}
    for camera_id, path in enumerate(get_video_paths(path_to_video_folder=synchronized_video_folder_path)):
        capture = cv2.VideoCapture(str(path))
        color_channels = 1 if capture.get(cv2.CAP_PROP_MONOCHROME) else 3
        video_configs[camera_id] = VideoConfig(
            camera_id=camera_id,
            camera_name=path.stem,
            num_frames= int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
            resolution=ImageResolution(height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
            color_channels=color_channels,
            framerate=capture.get(cv2.CAP_PROP_FPS),
            capture_fourcc=int(capture.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, byteorder=sys.byteorder).decode('utf-8'),
            video_path=path
        )
    if len(video_configs) == 0:
        raise RuntimeError("No video files found in video folder")
    return video_configs