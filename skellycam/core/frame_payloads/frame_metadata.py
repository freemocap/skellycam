import numpy as np
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE


def initialize_frame_metadata_rec_array(
        camera_config: CameraConfig,
        frame_number: int,
        timebase_mapping: TimebaseMapping
) -> np.recarray:
    # Create a record array with the correct shape (1,)
    result = np.recarray(1, dtype=FRAME_METADATA_DTYPE)

    # Assign values to the record array
    result.camera_config[0] = camera_config.to_numpy_record_array()[0]
    result.frame_number[0] = frame_number
    result.timestamps[0] = FrameLifespanTimestamps(timebase_mapping=timebase_mapping).to_numpy_record_array()[0]

    return result

class FrameMetadata(BaseModel):
    """
    A Pydantic model to represent the metadata associated with a frame of image data, we will build this from the numpy array once we've cleared the camera/shm whackiness.
    """
    frame_number: int
    camera_config: CameraConfig
    timestamps: FrameLifespanTimestamps

    @property
    def camera_id(self) -> str:
        return self.camera_config.camera_id


    @property
    def timestamp_ns(self) -> float:
        return self.timestamps.timestamp_local_unix_ms

    @classmethod
    def create_initial(cls, camera_config: CameraConfig, timebase_mapping:TimebaseMapping) -> "FrameMetadata":
        return cls(
            frame_number=-1,
            camera_config=camera_config,
            timestamps=FrameLifespanTimestamps(timebase_mapping=timebase_mapping),
        )
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
        )

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FrameMetadata to a numpy record array.
        """
        # Create a record array with the correct shape (1,) to match the expected structure
        result = np.recarray(1, dtype=FRAME_METADATA_DTYPE)

        # Assign values to the record array
        result.camera_config[0] = self.camera_config.to_numpy_record_array()[0]
        result.frame_number[0] = self.frame_number
        result.timestamps[0] = self.timestamps.to_numpy_record_array()[0]

        return result