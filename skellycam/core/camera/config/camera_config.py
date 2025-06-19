from typing import Tuple, Self, Any

import cv2
import numpy as np
from pydantic import BaseModel, Field, model_validator

from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.types.image_rotation_types import RotationTypes
from skellycam.core.types.numpy_record_dtypes import CAMERA_CONFIG_DTYPE
from skellycam.core.types.type_overloads import CameraIdString, BYTES_PER_MONO_PIXEL, CameraNameString
from skellycam.core.types.type_overloads import CameraIndex, CameraName
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


def get_video_file_type(fourcc_code: int) -> str:
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


class ParameterDifferencesModel(BaseModel):
    parameter_name: str
    self_value: Any
    other_value: Any


class SettableCameraParameters(BaseModel):
    exposure_mode: str
    exposure: int | str
    resolution: ImageResolution
    framerate: float
    rotation: RotationTypes


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
    exposure: int = Field(
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

    def to_settable_parameters(self) -> SettableCameraParameters:
        """
        Converts the CameraConfig to a SettableCameraParameters object.

        Returns
        -------
        SettableCameraParameters
            An object containing the parameters that can be set on the camera.
        """
        return SettableCameraParameters(
            exposure_mode=self.exposure_mode,
            exposure=self.exposure,
            resolution=self.resolution,
            framerate=self.framerate,
            rotation=self.rotation
        )

    def accept_settable_parameters(self, settable_parameters: SettableCameraParameters) -> None:
        """
        Accepts a SettableCameraParameters object and updates the CameraConfig accordingly.

        Parameters
        ----------
        settable_parameters : SettableCameraParameters
            The parameters to update the CameraConfig with.
        """
        self.exposure_mode = settable_parameters.exposure_mode
        self.exposure = settable_parameters.exposure
        self.resolution = settable_parameters.resolution
        self.rotation = settable_parameters.rotation

    def get_setting_differences(self, other: "CameraConfig") -> list[ParameterDifferencesModel]:
        """
        Returns a list of ParameterDifferencesModel objects containing the differences between this CameraConfig and another, but only for the fields that can be set (as defined in SettableCameraParameters).
        """
        self_dict = self.to_settable_parameters().model_dump()
        other_dict = other.to_settable_parameters().model_dump()

        diffs = []
        for key, self_value in self_dict.items():
            other_value = other_dict.get(key)
            if self_value != other_value:
                diffs.append(ParameterDifferencesModel(
                    parameter_name=key,
                    self_value=self_value,
                    other_value=other_value
                ))

        return diffs

    def to_numpy_record_array(self) -> np.recarray:
        rec_arr = np.recarray((1,), dtype=CAMERA_CONFIG_DTYPE)

        rec_arr.camera_id[0] = self.camera_id
        rec_arr.camera_index[0] = self.camera_index
        rec_arr.camera_name[0] = self.camera_name
        rec_arr.use_this_camera[0] = self.use_this_camera
        rec_arr.resolution_height[0] = self.resolution.height
        rec_arr.resolution_width[0] = self.resolution.width
        rec_arr.color_channels[0] = self.color_channels
        rec_arr.pixel_format[0] = self.pixel_format
        rec_arr.exposure_mode[0] = self.exposure_mode
        rec_arr.exposure[0] = self.exposure
        rec_arr.framerate[0] = round(self.framerate,4)
        rec_arr.rotation[0] = self.rotation.value
        rec_arr.capture_fourcc[0] = self.capture_fourcc
        rec_arr.writer_fourcc[0] = self.writer_fourcc

        return rec_arr

    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != CAMERA_CONFIG_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {CAMERA_CONFIG_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            camera_id=array.camera_id,
            camera_index=array.camera_index,
            camera_name=array.camera_name,
            use_this_camera=array.use_this_camera,
            resolution=ImageResolution(
                height=array.resolution_height,
                width=array.resolution_width
            ),
            color_channels=array.color_channels,
            pixel_format=array.pixel_format,
            exposure_mode=array.exposure_mode,
            exposure=array.exposure,
            framerate=array.framerate,
            rotation=RotationTypes(array.rotation),
            capture_fourcc=array.capture_fourcc,
            writer_fourcc=array.writer_fourcc
        )

    def __eq__(self, other: "CameraConfig") -> bool:
        """
        Compare two CameraConfig objects with tolerance for floating point values.

        Parameters
        ----------
        other : CameraConfig
            The CameraConfig to compare against

        Returns
        -------
        bool
            True if the configs are equal (with tolerance for floating point values)
        """
        self_dict = self.model_dump()
        other_dict = other.model_dump()

        # Define tolerance for floating point comparisons
        float_tolerance = 1e-3

        for key, self_value in self_dict.items():
            other_value = other_dict.get(key)

            # Special handling for floating point values
            if isinstance(self_value, float) and isinstance(other_value, float):
                if abs(self_value - other_value) > float_tolerance:
                    return False
            # For nested objects like resolution
            elif isinstance(self_value, dict) and isinstance(other_value, dict):
                for nested_key, nested_self_value in self_value.items():
                    nested_other_value = other_value.get(nested_key)
                    if isinstance(nested_self_value, float) and isinstance(nested_other_value, float):
                        if abs(nested_self_value - nested_other_value) > float_tolerance:
                            return False
                    elif nested_self_value != nested_other_value:
                        return False
            # For all other types, use standard equality
            elif self_value != other_value:
                return False

        return True

    def __sub__(self, other: "CameraConfig") -> list[ParameterDifferencesModel]:
        """
        Returns a list of differences between two CameraConfig objects, with tolerance for floating point values.

        Parameters
        ----------
        other : CameraConfig
            The CameraConfig to compare against

        Returns
        -------
        list[ParameterDifferencesModel]
            List of differences between the two configs
        """
        self_dict = self.model_dump()
        other_dict = other.model_dump()

        # Define tolerance for floating point comparisons
        float_tolerance = 1e-5

        diffs = []
        for key, self_value in self_dict.items():
            other_value = other_dict.get(key)

            # Special handling for floating point values
            if isinstance(self_value, float) and isinstance(other_value, float):
                if abs(self_value - other_value) > float_tolerance:
                    diffs.append(ParameterDifferencesModel(
                        parameter_name=key,
                        self_value=self_value,
                        other_value=other_value
                    ))
            # For nested objects like resolution
            elif isinstance(self_value, dict) and isinstance(other_value, dict):
                nested_diffs = []
                for nested_key, nested_self_value in self_value.items():
                    nested_other_value = other_value.get(nested_key)
                    if isinstance(nested_self_value, float) and isinstance(nested_other_value, float):
                        if abs(nested_self_value - nested_other_value) > float_tolerance:
                            nested_diffs.append((nested_key, nested_self_value, nested_other_value))
                    elif nested_self_value != nested_other_value:
                        nested_diffs.append((nested_key, nested_self_value, nested_other_value))

                if nested_diffs:
                    for nested_key, nested_self_value, nested_other_value in nested_diffs:
                        diffs.append(ParameterDifferencesModel(
                            parameter_name=f"{key}.{nested_key}",
                            self_value=nested_self_value,
                            other_value=nested_other_value
                        ))
            # For all other types, use standard equality
            elif self_value != other_value:
                diffs.append(ParameterDifferencesModel(
                    parameter_name=key,
                    self_value=self_value,
                    other_value=other_value
                ))

        return diffs

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


def validate_camera_configs(camera_configs: CameraConfigs) -> None:
    # Ensure camera_configs is a dictionary of CameraConfig instances
    if not isinstance(camera_configs, dict):
        raise TypeError(f"camera_configs must be a dictionary, got {type(camera_configs)} instead.")
    for camera_id, config in camera_configs.items():
        if not isinstance(config, CameraConfig):
            raise TypeError(
                f"Camera config for {camera_id} must be an instance of CameraConfig, got {type(config)} instead.")
        if camera_id != config.camera_id:
            raise ValueError(f"Camera ID mismatch: {camera_id} does not match config's camera_id {config.camera_id}.")

    # Ensure camera indexes are unique
    camera_indexes = [config.camera_index for config in camera_configs.values()]
    if len(camera_indexes) != len(set(camera_indexes)):
        raise ValueError("Camera indexes must be unique across all camera configurations.")


if __name__ == "__main__":
    print(CameraConfig(camera_index=0))
