import logging
import platform
from typing import List, Dict

from pydantic import BaseModel

from skellycam.core import CameraIndex, CameraName
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera_group.camera.config.default_config import DefaultCameraConfig
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution

logger = logging.getLogger(__name__)


class DeviceVideoFormat(BaseModel):
    """
    Information about a camera device's available video formats
    """

    width: int
    height: int
    pixel_format: str
    framerate: float


video_format_1080 = DeviceVideoFormat(
    width=1920,
    height=1080,
    pixel_format=DefaultCameraConfig.CAPTURE_FOURCC.value,
    framerate=DefaultCameraConfig.FRAMERATE.value
)
video_format_480 = DeviceVideoFormat(
    width=640,
    height=480,
    pixel_format=DefaultCameraConfig.CAPTURE_FOURCC.value,
    framerate=DefaultCameraConfig.FRAMERATE.value
)

video_format_720 = DeviceVideoFormat(
    width=1280,
    height=720,
    pixel_format=DefaultCameraConfig.CAPTURE_FOURCC.value,
    framerate=DefaultCameraConfig.FRAMERATE.value
)

DEFAULT_VIDEO_FORMATS = [video_format_1080, video_format_720, video_format_480]


class CameraDeviceInfo(BaseModel):
    """
    Selected information pulled out of a QCameraDevice object
    # TODO - deprecate `/camreas/detect/` route and move 'detection' responsibilities to client - remove all refrence to QT and Pyside
    """

    description: CameraName
    device_address: str
    cv2_port: int
    available_video_formats: List[DeviceVideoFormat]

    @property
    def available_resolutions(self) -> List[str]:
        """
        Get a list of all available resolutions, sorted from lowest ([0]) to highest ([-1])
        """
        all_resolutions = [
            ImageResolution(width=video_format.width, height=video_format.height)
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
    def from_pygrabber_device(cls, device_index: int, device_name: str):
        return cls(
            description=device_name,
            available_video_formats=DEFAULT_VIDEO_FORMATS,
            device_address=f"pygrabber_device_{device_index}",
            cv2_port=device_index
        )

    @classmethod
    def from_q_camera_device(cls, camera_number: int, camera):
        from PySide6.QtMultimedia import QCameraDevice
        if not isinstance(camera, QCameraDevice):
            raise ValueError(f"Expected QCameraDevice, got {type(camera)}")

        device_address = camera.id().data().decode("utf-8")
        try:
            if platform.system() == 'Windows' or platform.system() == 'Darwin':
                logger.trace(f"Windows detected, using camera number as cv2 port")
                cv2_port = camera_number
            else:
                logger.trace(f"Non-Windows detected, using camera address as cv2 port")
                cv2_port = device_address.split("video")[1]
        except Exception as e:
            cv2_port = camera_number

        return cls(
            description=f"{device_address} - {camera.description()}",
            available_video_formats=cls._get_available_video_formats(camera=camera),
            device_address=device_address,
            cv2_port=cv2_port
        )

    @classmethod
    def from_opencv_port_number(cls, port_number: int):
        device_address = f"opencv_port_{port_number}"
        description = f"OpenCV Camera {port_number}"

        return cls(
            description=description,
            device_address=device_address,
            cv2_port=port_number,
            available_video_formats=DEFAULT_VIDEO_FORMATS
        )

    @staticmethod
    def _get_available_video_formats(camera) -> List[DeviceVideoFormat]:
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


AvailableCameras = Dict[CameraIndex, CameraDeviceInfo]


def available_cameras_to_default_camera_configs(available_devices: AvailableCameras) -> CameraConfigs:
    return {camera_id: CameraConfig(camera_index=camera_id,
                                    camera_name=camera_info.description,
                                    ) for camera_id, camera_info in available_devices.items()}
