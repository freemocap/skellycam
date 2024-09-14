from pydantic import BaseModel
from typing import Union

from skellycam.opencv.camera.types.camera_id import CameraId


class CameraConfig(BaseModel):
    camera_id: CameraId = "0"
    exposure: Union[int, str] = -7  # Supports either an int or "auto" for exposure level
    resolution_width: int = 960
    resolution_height: int = 540
    framerate: int = 30
    # fourcc: str = "MP4V"
    fourcc: str = "MJPG"
    rotate_video_cv2_code: int = -1
    use_this_camera: bool = True
