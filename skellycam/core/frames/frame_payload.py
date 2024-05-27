from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, field_validator, ConfigDict

from skellycam.core.frames.frame_metadata import FRAME_METADATA_SHAPE, FRAME_METADATA_MODEL


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
        return cls(image=dto.image, metadata=dto.metadata)

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, metadata: np.ndarray):
        if metadata.shape != FRAME_METADATA_SHAPE:
            raise ValueError(f"Metadata shape mismatch - "
                             f"Expected: {FRAME_METADATA_SHAPE}, "
                             f"Actual: {metadata.shape}")
    @property
    def camera_id(self):
        return self.metadata[FRAME_METADATA_MODEL.CAMERA_ID]

    def __eq__(self, other: "FramePayload"):
        return np.array_equal(self.image, other.image) and np.array_equal(self.metadata, other.metadata)

    def __str__(self):
        print_str = (
            f"Camera{self.camera_id}:"
            f"\n\tFrame#{self.frame_number} - [height: {self.height}, width: {self.width}, color channels: {self.color_channels}]"
            f"\n\tPayload Size: {self.payload_size_in_kilobytes:.3f} KB (Hydrated: {self.image_data is not None}),"
            f"\n\tSince Previous: {self.time_since_last_frame_ns / 1e6:.3f}ms"
        )
        return print_str
