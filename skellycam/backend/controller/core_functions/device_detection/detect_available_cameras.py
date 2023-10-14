from pprint import pprint
from typing import List, Any, Dict

from PySide6.QtMultimedia import QMediaDevices, QCameraDevice
from pydantic import BaseModel


class VideoFormat(BaseModel):
    width: int
    height: int
    pixel_format: Any
    framerate: float


class CameraInfo(BaseModel):
    """
    Useful information pulled out of a QCameraDevice
    """
    description: str
    available_video_formats: List[VideoFormat]

    @property
    def available_resolutions(self) -> List[Dict[str, int]]:
        """
        Get a list of all available resolutions, sorted from lowest ([0]) to highest ([-1])
        """
        all_resolutions = [{"width": video_format.width, "height": video_format.height}
                           for video_format in self.available_video_formats]
        unique_resolutions = list(set([tuple(resolution.items()) for resolution in all_resolutions]))
        unique_resolutions.sort()
        return [dict(resolution) for resolution in unique_resolutions]

    @property
    def available_framerates(self) -> List[float]:
        """
        Get a list of all available framerates, sorted from lowest ([0]) to highest ([-1])
        """
        all_framerates = [video_format.framerate for video_format in self.available_video_formats]
        unique_framerates = list(set(all_framerates))
        unique_framerates.sort()
        return unique_framerates




    @classmethod
    def from_q_camera_device(cls, camera_number:int, camera: QCameraDevice):
        return cls(description= f"{camera_number} - {camera.description()}",
                   available_video_formats=cls._get_available_video_formats(camera=camera))

    @staticmethod
    def _get_available_video_formats(camera: QCameraDevice) -> List[VideoFormat]:
        available_video_formats = camera.videoFormats()
        video_formats = [VideoFormat(width=video_format.resolution().width(),
                               height=video_format.resolution().height(),
                               pixel_format=video_format.pixelFormat(),
                               framerate=video_format.maxFrameRate())
                   for video_format in available_video_formats]

        return video_formats


def detect_available_cameras() -> Dict[str, CameraInfo]:
    devices = QMediaDevices()
    available_cameras = devices.videoInputs()
    cameras = {}
    for camera_number, camera in enumerate(available_cameras):
        if camera.isNull():
            continue
        cameras[str(camera_number)] = CameraInfo.from_q_camera_device(camera_number=camera_number,
                                                                      camera=camera)
    return cameras


if __name__ == "__main__":
    cameras_out = detect_available_cameras()
    pprint(cameras_out, indent=4)