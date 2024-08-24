from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.frames.payload_models.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE


@dataclass
class FramePayloadDTO:
    """
    Lightweight data transfer object for FramePayload
    """
    image: np.ndarray
    metadata: np.ndarray


class FramePayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image: np.ndarray
    metadata: np.ndarray

    @classmethod
    def from_dto(cls, dto: FramePayloadDTO):
        image = dto.image
        metadata = dto.metadata
        instance = cls(image=image, metadata=metadata)
        if instance.metadata.shape != FRAME_METADATA_SHAPE:
            raise ValueError(f"Metadata shape mismatch - "
                             f"Expected: {FRAME_METADATA_SHAPE}, "
                             f"Actual: {metadata.shape}")
        return instance

    @property
    def camera_id(self):
        return self.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]

    @property
    def frame_number(self):
        return self.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]

    @property
    def height(self):
        return self.image.shape[0]

    @property
    def width(self):
        return self.image.shape[1]

    def __eq__(self, other: "FramePayload"):
        return np.array_equal(self.image, other.image) and np.array_equal(self.metadata, other.metadata)

    def __str__(self):
        print_str = (
            f"Camera{self.camera_id}: Image shape: {self.image.shape}, "
        )
        return print_str
