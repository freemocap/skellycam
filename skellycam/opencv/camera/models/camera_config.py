from pydantic import BaseModel

from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam.system.environment.home_dir import os_independent_home_dir


class CameraConfig(BaseModel):
    camera_id: CameraId = 0
    exposure: int = -7
    resolution_width: int = 1280
    resolution_height: int = 720
    # fourcc: str = "MP4V"
    fourcc: str = "MJPG"
    rotate_video_cv2_code: int = None
    use_this_camera: bool = True
