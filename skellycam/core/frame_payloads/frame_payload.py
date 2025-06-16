import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL


class FramePayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: np.ndarray
    metadata: np.ndarray

    @property
    def camera_id(self):
        return self.metadata[FRAME_METADATA_MODEL.CAMERA_INDEX.value]

    @property
    def frame_number(self):
        return self.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]

    @property
    def timestamp_ns(self) -> int:
        """
        De facto timestamp for this frame is defined as the average of the pre-grab and post-grab timestamps (i.e. the hypothetical moment the image was grabbed).
        """
        return int((self.metadata[FRAME_METADATA_MODEL.PRE_GRAB_TIMESTAMP_NS.value] + self.metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value]) // 2)
    @property
    def height(self):
        return self.image.shape[0]

    @property
    def width(self):
        return self.image.shape[1]

    @property
    def frame_metadata(self) -> FrameMetadata:
        return FrameMetadata.from_frame_metadata_array(self.metadata)


    def __eq__(self, other: "FramePayload"):
        return np.array_equal(self.image, other.image) and np.array_equal(self.metadata, other.metadata)

    def __str__(self):
        print_str = (
            f"Camera {self.camera_id}: Image shape: {self.image.shape}, "
        )
        return print_str
