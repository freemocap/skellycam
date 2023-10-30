from pydantic import BaseModel, Field

from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.image_rotation_types import RotationTypes
from skellycam.models.cameras.video_resolution import VideoResolution


class CameraConfig(BaseModel):
    camera_id: CameraId = Field(description="The id of the camera to use, "
                                            "e.g. cv2.VideoCapture uses `0` for the first camera")

    use_this_camera: bool = Field(default=True,
                                  description="Whether or not to use this camera for streaming/recording")
    resolution: VideoResolution = Field(default=VideoResolution(width=1280,
                                                                height=720),
                                        description="The current resolution of the camera, in pixels.")
    exposure: int = Field(default=-6,
                          description="The exposure of the camera using the opencv convention - "
                                      "https://www.kurokesu.com/main/2020/05/22/uvc-camera-exposure-timing-in-opencv/")
    framerate: float = Field(default=30,
                             description="The framerate of the camera (in frames per second).")

    rotation: RotationTypes = Field(default=RotationTypes.NO_ROTATION,
                                    description="The rotation to apply to the images "
                                                "of this camera (after they are captured)")
    capture_fourcc: str = Field(default="MJPG",  # TODO - compare performance of MJPG vs H264 vs whatever else
                                description="The fourcc code to use for the video codec in the `cv2.VideoCapture` object")

    writer_fourcc: str = Field(default="XVID",  # Save videos as XVID/avi so video will still work even if crashses
                               description="The fourcc code to use for the video codec in the `cv2.VideoWriter` object")

    @property
    def orientation(self) -> str:
        return self.resolution.orientation

    @property
    def aspect_ratio(self) -> float:
        return self.resolution.aspect_ratio
