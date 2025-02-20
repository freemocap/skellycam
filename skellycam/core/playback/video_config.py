from pathlib import Path
from typing import Dict

import cv2

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellytracker.utilities.get_video_paths import get_video_paths

from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution


class VideoConfig(CameraConfig):
    video_path: Path
    exposure_mode: str = ""

VideoConfigs = Dict[CameraId, VideoConfig]


def load_video_configs_from_folder(synchronized_video_folder_path: str | Path) -> VideoConfigs:
    video_configs = {}
    for camera_id, path in enumerate(get_video_paths(path_to_video_folder=synchronized_video_folder_path)):
        capture = cv2.VideoCapture(str(path))
        color_channels = 1 if capture.get(cv2.CAP_PROP_MONOCHROME) else 3
        video_configs[camera_id] = VideoConfig(
            camera_id=camera_id,
            camera_name=path.stem,

            resolution=ImageResolution(height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
            color_channels=color_channels,
            framerate=capture.get(cv2.CAP_PROP_FPS),
            capture_fourcc=int(capture.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, byteorder=sys.byteorder).decode('utf-8'),
            video_path=path
        )
    return video_configs