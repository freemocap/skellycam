from typing import Tuple, Self

import cv2
from pydantic import BaseModel, Field, model_validator

from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera.config.image_rotation_types import RotationTypes
from skellycam.core.types import CameraIdString, BYTES_PER_MONO_PIXEL, CameraNameString
from skellycam.core.types import CameraIndex, CameraName
from skellycam.system.diagnostics.recommend_camera_exposure_setting import ExposureModes

DEFAULT_IMAGE_HEIGHT: int = 720
DEFAULT_IMAGE_WIDTH: int = 1280
DEFAULT_IMAGE_CHANNELS: int = 3
DEFAULT_IMAGE_SHAPE: tuple = (DEFAULT_IMAGE_HEIGHT, DEFAULT_IMAGE_WIDTH, DEFAULT_IMAGE_CHANNELS)
DEFAULT_CAMERA_INDEX: CameraIndex = CameraIndex(0)
DEFAULT_CAMERA_ID: CameraIdString = "000"
DEFAULT_CAMERA_NAME: CameraNameString = "Default Camera"
DEFAULT_RESOLUTION: ImageResolution = ImageResolution(height=DEFAULT_IMAGE_HEIGHT, width=DEFAULT_IMAGE_WIDTH)
DEFAULT_EXPOSURE_MODE: str = ExposureModes.MANUAL.name
DEFAULT_EXPOSURE: int = -7
DEFAULT_FRAMERATE: float = 30.0
DEFAULT_ROTATION: RotationTypes = RotationTypes.NO_ROTATION
DEFAULT_CAPTURE_FOURCC: str = "MJPG"  # skellycam/system/diagnostics/run_cv2_video_capture_diagnostics.py
DEFAULT_WRITER_FOURCC: str = "X264"  # Need set up our installer and whanot so we can us `X264` (or H264, if its easier to set up) skellycam/system/diagnostics/run_cv2_video_writer_diagnostics.py

def get_video_file_type(fourcc_code: int) ->str:
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
    camera_id: CameraIdString = Field(
        default=DEFAULT_CAMERA_ID,
        description="The ID of the camera. May be used for display purposes, must be unique.")

    camera_index: CameraIndex = Field(
        default=DEFAULT_CAMERA_INDEX,
        description="The index of the camera in the system. This is used to create the `cv2.VideoCapture` object. ")

    camera_name: CameraName = Field(
        default=DEFAULT_CAMERA_NAME,
        description="The name of the camera, if known. May be used for display purposes, does not need to be unique.",
    )
    use_this_camera: bool = Field(
        default=True,
        description="Whether to use this camera in the camera group. If False, the be removed from the camera group when convient within the frame loop. ",
    )
    resolution: ImageResolution = Field(
        default=DEFAULT_RESOLUTION,
        description="The current resolution of the camera, in pixels.",
    )
    color_channels: int = Field(
        default=DEFAULT_IMAGE_CHANNELS,
        description="The number of color channels in the image (3 for RGB, 1 for monochrome)",
    )

    # TODO - Handle options other than RGB
    pixel_format: str = Field(default="RGB",
                              description="How to interpret the color channels")

    exposure_mode: str = Field(default=DEFAULT_EXPOSURE_MODE,
                               description="The exposure mode to use for the camera, "
                                           "AUTO for device automatic exposure, "
                                           "MANUAL to set the exposure manually, "
                                           "or RECOMMENDED to use the find the setting "
                                           "that puts mean pixel intensity at 128 (255/2).")
    exposure: int | str = Field(
        default=DEFAULT_EXPOSURE,
        description="The exposure of the camera using the opencv convention (the number is the exposure time in ms, raised to the power of -2). "
                    "https://www.kurokesu.com/main/2020/05/22/uvc-camera-exposure-timing-in-opencv/ "
                    " (Hint! Set this as low as possible to avoid blur."
                    " Mocap likes BRIGHT environments and FAST/LOW exposure settings!)",
    )

    framerate: float = Field(default=DEFAULT_FRAMERATE,
                             description="The frame rate of the camera (in frames per second).")

    rotation: RotationTypes = Field(
        default=DEFAULT_ROTATION,
        description="The rotation to apply to the images of this camera (after they are captured)",
    )
    capture_fourcc: str = Field(
        default=DEFAULT_CAPTURE_FOURCC,
        description="The fourcc code to use for the video codec in the `cv2.VideoCapture` object",
    )

    writer_fourcc: str = Field(
        default=DEFAULT_WRITER_FOURCC,
        description="The fourcc code to use for the video codec in the `cv2.VideoWriter` object",
    )

    @model_validator(mode="after")
    def validate(self) -> Self:
        if self.camera_name is DEFAULT_CAMERA_NAME:
            self.camera_name = f"Camera-{self.camera_id}"
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


def default_camera_configs_factory():
    return {
        "dummy": CameraConfig()
    }

CameraConfigs = dict[CameraIdString, CameraConfig]

def validate_camera_configs(camera_configs: CameraConfigs| CameraConfig | list[CameraConfig]) -> None:
    if isinstance(camera_configs, CameraConfig):
        camera_configs = {camera_configs.camera_id: camera_configs}
    elif isinstance(camera_configs, list):
        camera_configs = {config.camera_id: config for config in camera_configs}

    # Ensure camera_configs is a dictionary of CameraConfig instances
    if not isinstance(camera_configs, dict):
        raise TypeError(f"camera_configs must be a dictionary, got {type(camera_configs)} instead.")
    for camera_id, config in camera_configs.items():
        if not isinstance(config, CameraConfig):
            raise TypeError(f"Camera config for {camera_id} must be an instance of CameraConfig, got {type(config)} instead.")
        if camera_id != config.camera_id:
            raise ValueError(f"Camera ID mismatch: {camera_id} does not match config's camera_id {config.camera_id}.")

    #Ensure camera indexes are unique
    camera_indexes = [config.camera_index for config in camera_configs.values()]
    if len(camera_indexes) != len(set(camera_indexes)):
        raise ValueError("Camera indexes must be unique across all camera configurations.")


if __name__ == "__main__":
    print(CameraConfig(camera_index=0))
