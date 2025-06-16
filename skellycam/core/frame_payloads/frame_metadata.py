import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimeBaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE


def initialize_frame_metadata_rec_array(
        camera_config: CameraConfig,
        frame_number: int,   ) -> np.recarray:

    return np.rec.array(
        (camera_config.to_numpy_record_array(),
         frame_number,
         FrameLifespanTimestamps().to_numpy_record_array()),
        dtype=FRAME_METADATA_DTYPE
    )

class FrameMetadata(BaseModel):
    """
    A Pydantic model to represent the metadata associated with a frame of image data, we will build this from the numpy array once we've cleared the camera/shm whackiness.
    """
    frame_number: int
    camera_config: CameraConfig
    timestamps: FrameLifespanTimestamps
    timebase_mapping: TimeBaseMapping = Field(default_factory=TimeBaseMapping, description=TimeBaseMapping.__doc__)

    @property
    def camera_id(self) -> str:
        return self.camera_config.camera_id


    @property
    def timestamp_ns(self) -> int:
        return (self.timestamps.post_grab_timestamp_ns-self.timestamps.post_grab_timestamp_ns)//2

    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_METADATA_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_METADATA_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            frame_number=array.frame_number,
            camera_config=CameraConfig.from_numpy_record_array(array.camera_config),
            timestamps=FrameLifespanTimestamps.from_numpy_record_array(array.timestamps),
            timebase_mapping=TimeBaseMapping.from_numpy_record_array(array.timebase_mapping)
        )

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FrameMetadata to a numpy record array.
        """
        return np.rec.array(
            (self.camera_config.to_numpy_record_array(),
             self.frame_number,
             self.timestamps.to_numpy_record_array(),
             self.timebase_mapping.to_numpy_record_array()),
            dtype=FRAME_METADATA_DTYPE
        )
