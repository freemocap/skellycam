from enum import Enum
from typing import Any, Dict, Optional, List

import cv2
from pydantic import BaseModel, Field, PositiveFloat, NegativeInt, root_validator

from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.cameras.camera_id import CameraId
from skellycam.data_models.cameras.video_resolution import VideoResolution


class RotationType(Enum):
    NO_ROTATION = 0
    CLOCKWISE_90 = cv2.ROTATE_90_CLOCKWISE
    COUNTERCLOCKWISE_90 = cv2.ROTATE_90_COUNTERCLOCKWISE
    ROTATE_180 = cv2.ROTATE_180

    def __str__(self):
        match self:
            case RotationType.NO_ROTATION:
                return "No rotation"
            case RotationType.CLOCKWISE_90:
                return "Clockwise 90 degrees"
            case RotationType.COUNTERCLOCKWISE_90:
                return "Counterclockwise 90 degrees"
            case RotationType.ROTATE_180:
                return "Rotate 180 degrees"

        raise ValueError(f"Unknown rotation type: {self}")


class CameraConfig(BaseModel):
    camera_id: CameraId = Field(description="The id of the camera to use, "
                                            "e.g. cv2.VideoCapture uses `0` for the first camera")

    use_this_camera: bool = Field(default=True,
                                  description="Whether or not to use this camera for streaming/recording")

    resolution: VideoResolution = Field(default=VideoResolution(width=1280, height=720),
                                        description="The current resolution of the camera, in pixels.")
    framerate: PositiveFloat = Field(default=30,
                                     description="The framerate of the camera (in frames per second).")
    exposure: NegativeInt = Field(default=-7,
                                  description="The exposure of the camera using the opencv convention - "
                                              "https://www.kurokesu.com/main/2020/05/22/uvc-camera-exposure-timing-in-opencv/")
    rotation: RotationType = Field(default=RotationType.NO_ROTATION,
                                   description="The rotation to apply to the images "
                                               "of this camera (after they are captured)")
    fourcc: str = Field(default="MP4V",
                        description="The fourcc code to use for the video codec - `MP4V` is the default,  "
                                    "but it would be interesting to try `MJPG1, `H264`, etc")
    available_resolutions:Optional[List[VideoResolution]]
    available_framerates:Optional[List[PositiveFloat]]

    @classmethod
    def from_id(cls, camera_id: CameraId):
        return cls(camera_id=camera_id)

    @classmethod
    def from_dict(cls, camera_config_dict: Dict[str, Any]):
        return cls(**camera_config_dict,
                   available_resolutions=[camera_config_dict.get("resolution")],
                   available_framerates=[camera_config_dict.get("framerate")])

    @classmethod
    def from_camera_device_info(cls, camera_device_info: CameraDeviceInfo):
        return cls(device_info=camera_device_info,
                   framerate=camera_device_info.available_framerates[-1],
                   available_resolutions=camera_device_info.available_resolutions,
                   available_framerates=camera_device_info.available_framerates)
