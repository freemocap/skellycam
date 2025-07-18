import numpy as np
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE




class FrameMetadata(BaseModel):
    """
    A Pydantic model to represent the metadata associated with a frame of image data, we will build this from the numpy array once we've cleared the camera/shm whackiness.
    """
    frame_number: int
    camera_config: CameraConfig
    timestamps: FrameTimestamps


    @property
    def camera_id(self) -> str:
        return self.camera_config.camera_id

    @classmethod
    def from_recarray(cls, array: np.recarray):
        if array.dtype != FRAME_METADATA_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_METADATA_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            frame_number=array.frame_number[0],
            camera_config=CameraConfig.from_numpy_record_array(array.camera_config),
            timestamps=FrameTimestamps.from_frame_timestamps_recarray(array.timestamps),
        )

