from typing import Tuple, Dict, Optional, Self

import cv2
from pydantic import BaseModel, Field, model_validator

from skellycam.core import BYTES_PER_MONO_PIXEL, CameraName
from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.default_config import DefaultCameraConfig
from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes


def get_video_file_type(fourcc_code: int) -> Optional[str]:
    """
    Get the video file type based on an OpenCV FOURCC code.

    Parameters
    ----------
    fourcc_code : int
        The FOURCC code representing the codec.

    Returns
    -------
    Optional[str]
        The file extension of the video file type, or None if not recognized.

    Examples
    --------
    >>> get_video_file_type(cv2.VideoWriter_fourcc(*'mp4v'))
    '.mp4'
    """
    fourcc_to_extension = {
        cv2.VideoWriter_fourcc(*'MP4V'): '.mp4',
        cv2.VideoWriter_fourcc(*'H264'): '.mp4',
        cv2.VideoWriter_fourcc(*'X264'): '.mp4',

        cv2.VideoWriter_fourcc(*'XVID'): '.avi',
        cv2.VideoWriter_fourcc(*'DIVX'): '.avi',

        cv2.VideoWriter_fourcc(*'MJPG'): '.mjpeg',
        cv2.VideoWriter_fourcc(*'VP80'): '.webm',
        cv2.VideoWriter_fourcc(*'THEO'): '.ogv',
        cv2.VideoWriter_fourcc(*'WMV1'): '.wmv',
        cv2.VideoWriter_fourcc(*'WMV2'): '.wmv',
        cv2.VideoWriter_fourcc(*'FLV1'): '.flv',
    }

    file_format = fourcc_to_extension.get(fourcc_code, None)
    if file_format is None:
        raise ValueError(f"Unrecognized FOURCC code: {fourcc_code}")
    return file_format


class CameraConfig(BaseModel):
    camera_id: CameraId = Field(
        default=DefaultCameraConfig.CAMERA_ID.value,
        description="The id of the camera to use, e.g. cv2.VideoCapture uses `0` for the first camera",
    )
    camera_name: CameraName = Field(
        default=DefaultCameraConfig.CAMERA_NAME.value,
        description="The name of the camera, if known",
    )

    use_this_camera: bool = Field(
        default=DefaultCameraConfig.USE_THIS_CAMERA.value,
        description="Whether or not to use this camera for streaming/recording",
    )
    resolution: ImageResolution = Field(
        default=DefaultCameraConfig.RESOLUTION.value,
        description="The current resolution of the camera, in pixels.",
    )
    color_channels: int = Field(
        default=DefaultCameraConfig.COLOR_CHANNELS.value,
        description="The number of color channels in the image (3 for RGB, 1 for monochrome)",
    )

    # TODO - Handle options other than RGB
    pixel_format: str = Field(default="RGB",
                              description="How to interpret the color channels")

    exposure_mode: str = Field(default=DefaultCameraConfig.EXPOSURE_MODE.value,
                               description="The exposure mode to use for the camera, "
                                           "AUTO for device automatic exposure, "
                                           "MANUAL to set the exposure manually, "
                                           "or RECOMMENDED to use the find the setting "
                                           "that puts mean pixel intensity at 128 (255/2).")
    exposure: int | str = Field(
        default=DefaultCameraConfig.EXPOSURE.value,
        description="The exposure of the camera using the opencv convention (the number is the exposure time in ms, raised to the power of -2). "
                    "https://www.kurokesu.com/main/2020/05/22/uvc-camera-exposure-timing-in-opencv/ "
                    " (Hint! Set this as low as possible to avoid blur."
                    " Mocap likes BRIGHT environments and FAST/LOW exposure settings!)",
    )

    framerate: float = Field(default=DefaultCameraConfig.FRAMERATE.value,
                             description="The frame rate of the camera (in frames per second).")

    rotation: RotationTypes = Field(
        default=DefaultCameraConfig.ROTATION.value,
        description="The rotation to apply to the images of this camera (after they are captured)",
    )
    capture_fourcc: str = Field(
        default=DefaultCameraConfig.CAPTURE_FOURCC.value,
        description="The fourcc code to use for the video codec in the `cv2.VideoCapture` object",
    )

    writer_fourcc: str = Field(
        default=DefaultCameraConfig.WRITER_FOURCC.value,
        description="The fourcc code to use for the video codec in the `cv2.VideoWriter` object",
    )

    @model_validator(mode="after")
    def validate(self) -> Self:
        if self.camera_name is DefaultCameraConfig.CAMERA_NAME.value:
            self.camera_name = f"Camera-{self.camera_id}"
        self.camera_id = CameraId(self.camera_id)
        return self

    @property
    def orientation(self) -> str:
        return self.resolution.orientation

    @property
    def aspect_ratio(self) -> float:
        return self.resolution.aspect_ratio

    @property
    def image_shape(self) -> Tuple[int, ...]:
        if self.color_channels == 1:
            return self.resolution.height, self.resolution.width
        else:
            return self.resolution.height, self.resolution.width, self.color_channels

    @property
    def image_size_bytes(self) -> int:
        return self.resolution.width * self.resolution.height * self.color_channels * BYTES_PER_MONO_PIXEL

    @property
    def video_file_extension(self) -> str:
        return get_video_file_type(cv2.VideoWriter_fourcc(*self.writer_fourcc))

    def __eq__(self, other: "CameraConfig") -> bool:
        return self.model_dump() == other.model_dump()

    def __str__(self):
        out_str = f"\n\tBASE CONFIG:\n"
        for key, value in self.model_dump().items():
            out_str += f"\t\t{key} ({type(value).__name__}): {value} \n"
        out_str += "\tCOMPUTED:\n"
        out_str += f"\t\taspect_ratio(w/h): {self.aspect_ratio:.3f}\n"
        out_str += f"\t\torientation: {self.orientation}\n"
        out_str += f"\t\timage_shape: {self.image_shape}\n"
        out_str += f"\t\timage_size: {self.image_size_bytes / 1024:.3f}KB\n"
        return out_str


CameraConfigs = dict[CameraId|str, CameraConfig]


def default_camera_configs_factory():
    return {
        DefaultCameraConfig.CAMERA_ID: CameraConfig()
    }


if __name__ == "__main__":
    print(CameraConfig(camera_id=0))
