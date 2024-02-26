import platform
from typing import List, Any

from PySide6.QtMultimedia import QCameraDevice
from pydantic import BaseModel

from skellycam.backend.models.cameras.video_resolution import VideoResolution

import logging
logger = logging.getLogger(__name__)

class DeviceVideoFormat(BaseModel):
    """
    A bit redundant with `CameraConfig`, but this is specifically to
    be used by the `CameraDeviceInfo` class as it's main purpose is to
    be a data structure to hold information about a camera's available
    video formats (as reported by `QCameraDevice.videoFormats()`)
    """

    width: int
    height: int
    pixel_format: Any
    framerate: float


class CameraDeviceInfo(BaseModel):
    """
    Useful information pulled out of a QCameraDevice
    """

    description: str
    device_address:str
    cv2_port: int
    available_video_formats: List[DeviceVideoFormat]

    @property
    def available_resolutions(self) -> List[str]:
        """
        Get a list of all available resolutions, sorted from lowest ([0]) to highest ([-1])
        """
        all_resolutions = [
            VideoResolution(width=video_format.width, height=video_format.height)
            for video_format in self.available_video_formats
        ]
        unique_resolutions = list(set(all_resolutions))
        unique_resolutions.sort()
        return [str(unique_resolution) for unique_resolution in unique_resolutions]

    @property
    def available_framerates(self) -> List[float]:
        """
        Get a list of all available framerates, sorted from lowest ([0]) to highest ([-1])
        """
        all_framerates = [
            video_format.framerate for video_format in self.available_video_formats
        ]
        unique_framerates = list(set(all_framerates))
        unique_framerates.sort()
        return unique_framerates

    @classmethod
    def from_q_camera_device(cls, camera_number: int, camera: QCameraDevice):
        device_address =camera.id().data().decode("utf-8")
        if platform.system() == 'Windows':
            logger.debug(f"Windows detected, using camera number as cv2 port")
            cv2_port = camera_number
        else:
            logger.trace(f"Non-Windows detected, using camera address as cv2 port")
            cv2_port = device_address.split("video")[1]
        return cls(
            description=f"{device_address} - {camera.description()}",
            available_video_formats=cls._get_available_video_formats(camera=camera),
            device_address=device_address,
            cv2_port=cv2_port
        )

    @staticmethod
    def _get_available_video_formats(camera: QCameraDevice) -> List[DeviceVideoFormat]:
        available_video_formats = camera.videoFormats()
        video_formats = [
            DeviceVideoFormat(
                width=video_format.resolution().width(),
                height=video_format.resolution().height(),
                pixel_format=video_format.pixelFormat(),
                framerate=video_format.maxFrameRate(),
            )
            for video_format in available_video_formats
        ]

        return video_formats

    def __str__(self):
        return f"{self.description}"
