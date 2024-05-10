from typing import Tuple, Self

from pydantic import BaseModel, Field, model_validator, field_validator

from skellycam.core import BYTES_PER_PIXEL
from skellycam.core import CameraId
from skellycam.core.detection.image_resolution import ImageResolution
from skellycam.core.detection.image_rotation_types import RotationTypes


class CameraConfig(BaseModel):
    camera_id: CameraId = Field(
        default=CameraId(0),
        description="The id of the camera to use, "
                    "e.g. cv2.VideoCapture uses `0` for the first camera",
    )

    use_this_camera: bool = Field(
        default=True,
        description="Whether or not to use this camera for streaming/recording",
    )
    resolution: ImageResolution = Field(
        default=ImageResolution(width=1920, height=1080),
        description="The current resolution of the camera, in pixels.",
    )
    color_channels: int = Field(
        default=3,
        description="The number of color channels in the image (3 for RGB, 1 for monochrome)", )

    exposure: int = Field(
        default=-7,
        description="The exposure of the camera using the opencv convention - "
                    "https://www.kurokesu.com/main/2020/05/22/uvc-camera-exposure-timing-in-opencv/",
    )

    framerate: float = Field(
        default=30, description="The framerate of the camera (in frames per second)."
    )

    rotation: RotationTypes = Field(
        default=RotationTypes.NO_ROTATION,
        description="The rotation to apply to the images "
                    "of this camera (after they are captured)",
    )
    capture_fourcc: str = Field(
        default="MJPG",  # TODO - compare performance of MJPG vs H264 vs whatever else
        description="The fourcc code to use for the video codec in the `cv2.VideoCapture` object",
    )

    writer_fourcc: str = Field(
        default="MP4V",  # TODO - compare performance of MJPG vs H264 vs whatever else
        description="The fourcc code to use for the video codec in the `cv2.VideoWriter` object",
    )

    @field_validator('camera_id', mode="before")
    @classmethod
    def convert_camera_id(cls, v):
        return CameraId(v)


    @property
    def orientation(self) -> str:
        return self.resolution.orientation

    @property
    def aspect_ratio(self) -> float:
        return self.resolution.aspect_ratio

    @property
    def image_shape(self) -> Tuple[int, ...]:
        if self.color_channels == 1:
            return self.resolution.width, self.resolution.height
        else:
            return self.resolution.width, self.resolution.height, self.color_channels

    @property
    def image_size_bytes(self) -> int:
        return self.resolution.height * self.resolution.width * self.color_channels * BYTES_PER_PIXEL

    def __eq__(self, other):
        return self.dict() == other.dict()

    def __str__(self):
        out_str = f"BASE CONFIG:\n"
        for key, value in self.dict().items():
            out_str += f"\t{key} ({type(value).__name__}): {value} \n"
        out_str += "COMPUTED:\n"
        out_str += f"\taspect_ratio(w/h): {self.aspect_ratio:.3f}\n"
        out_str += f"\torientation: {self.orientation}\n"
        out_str += f"\timage_shape: {self.image_shape}\n"
        out_str += f"\timage_size: {self.image_size_bytes / 1024:.3f}KB"
        return out_str


if __name__ == "__main__":
    print(CameraConfig(camera_id=0))
