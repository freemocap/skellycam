import logging
import time

import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE

logger = logging.getLogger(__name__)

class FrameTimestamps(BaseModel):
    timebase_mapping:TimebaseMapping
    frame_initialized_ns: int = Field(default_factory=time.perf_counter_ns)
    pre_frame_grab_ns: int = 0
    post_frame_grab_ns: int = 0
    pre_frame_retrieve_ns: int = 0
    post_frame_retrieve_ns: int = 0
    pre_copy_to_camera_shm_ns: int = 0 #NOTE - can't measure pre/post here because can't edit in the shm!
    pre_retrieve_from_camera_shm_ns: int = 0
    post_retrieve_from_camera_shm_ns: int = 0
    pre_copy_to_multiframe_shm_ns: int = 0 # NOTE - ditto above
    pre_retrieve_from_multiframe_shm_ns: int = 0
    post_retrieve_from_multiframe_shm_ns: int = 0
    
    @property
    def timestamp_ns(self) -> int:
        """
        Using the midpoint between pre and post grab timestamps to represent the frame's timestamp.
        """
        if not self.pre_frame_grab_ns or not self.post_frame_grab_ns:
            raise ValueError("pre_frame_retrieve_ns and post_frame_grab_ns cannot be None")
        return (self.post_frame_grab_ns + self.pre_frame_grab_ns) // 2


    @property
    def durations(self) -> 'FrameDurations':
        """
        Get a helper object that calculates various duration metrics.
        """
        return FrameDurations(timestamps=self)

    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            frame_initialized_ns=array.frame_initialized_ns,
            pre_frame_grab_ns=array.pre_frame_grab_ns,
            post_frame_grab_ns=array.post_frame_grab_ns,
            pre_frame_retrieve_ns=array.pre_frame_retrieve_ns,
            post_frame_retrieve_ns=array.post_frame_retrieve_ns,
            pre_copy_to_camera_shm_ns=array.pre_copy_to_camera_shm_ns,
            pre_retrieve_from_camera_shm_ns=array.pre_retrieve_from_camera_shm_ns,
            post_retrieve_from_camera_shm_ns=array.post_retrieve_from_camera_shm_ns,
            pre_copy_to_multiframe_shm_ns=array.pre_copy_to_multiframe_shm_ns,
            pre_retrieve_from_multiframe_shm_ns=array.pre_retrieve_from_multiframe_shm_ns,
            post_retrieve_from_multiframe_shm_ns=array.post_retrieve_from_multiframe_shm_ns,
            timebase_mapping=TimebaseMapping.from_numpy_record_array(array.timebase_mapping)
        )

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FrameLifespanTimestamps to a numpy record array.
        """
        # Create a record array with the correct shape (1,)
        result = np.recarray(1, dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

        # Assign values to the record array
        result.timebase_mapping[0] = self.timebase_mapping.to_numpy_record_array()[0]
        result.frame_initialized_ns[0] = self.frame_initialized_ns
        result.pre_frame_grab_ns[0] = self.pre_frame_grab_ns
        result.post_frame_grab_ns[0] = self.post_frame_grab_ns
        result.pre_frame_retrieve_ns[0] = self.pre_frame_retrieve_ns
        result.post_frame_retrieve_ns[0] = self.post_frame_retrieve_ns
        result.pre_copy_to_camera_shm_ns[0] = self.pre_copy_to_camera_shm_ns
        result.pre_retrieve_from_camera_shm_ns[0] = self.pre_retrieve_from_camera_shm_ns
        result.post_retrieve_from_camera_shm_ns[0] = self.post_retrieve_from_camera_shm_ns
        result.pre_copy_to_multiframe_shm_ns[0] = self.pre_copy_to_multiframe_shm_ns
        result.pre_retrieve_from_multiframe_shm_ns[0] = self.pre_retrieve_from_multiframe_shm_ns
        result.post_retrieve_from_multiframe_shm_ns[0] = self.post_retrieve_from_multiframe_shm_ns

        return result



class FrameDurations(BaseModel):
    """
    Helper class for FrameTimestamps that calculates various duration metrics
    between different timestamp points in the frame lifecycle.
    """
    timestamps: FrameTimestamps

    @computed_field
    @property
    def idle_before_grab_ns(self) -> int:
        """Time between frame initialization and the start of the grab operation."""
        if self.timestamps.frame_initialized_ns and self.timestamps.pre_frame_grab_ns:
            return self.timestamps.pre_frame_grab_ns - self.timestamps.frame_initialized_ns
        return -1

    @computed_field
    @property
    def during_frame_grab_ns(self) -> int:
        """Time spent in the grab operation."""
        if self.timestamps.post_frame_grab_ns and self.timestamps.pre_frame_grab_ns:
            return self.timestamps.post_frame_grab_ns - self.timestamps.pre_frame_grab_ns
        return -1

    @computed_field
    @property
    def idle_before_retrieve_ns(self)-> int:
        if self.timestamps.pre_frame_retrieve_ns and self.timestamps.post_frame_grab_ns:
            return self.timestamps.pre_frame_retrieve_ns - self.timestamps.post_frame_grab_ns
        return -1

    @computed_field
    @property
    def during_frame_retrieve_ns(self) -> int:
        """Time spent in the retrieve operation."""
        if self.timestamps.post_frame_retrieve_ns and self.timestamps.pre_frame_retrieve_ns:
            return self.timestamps.post_frame_retrieve_ns - self.timestamps.pre_frame_retrieve_ns
        return -1

    @computed_field
    @property
    def idle_before_copy_to_camera_shm_ns(self) -> int:
        """Time between frame retrieval and copying to camera shared memory."""
        if self.timestamps.pre_copy_to_camera_shm_ns and self.timestamps.post_frame_retrieve_ns:
            return self.timestamps.pre_copy_to_camera_shm_ns - self.timestamps.post_frame_retrieve_ns
        return -1

    @computed_field
    @property
    def stored_in_camera_shm_ns(self) -> int:
        """Time spent in the camera shared memory buffer."""
        if self.timestamps.post_retrieve_from_camera_shm_ns and self.timestamps.pre_copy_to_camera_shm_ns:
            return self.timestamps.post_retrieve_from_camera_shm_ns - self.timestamps.pre_copy_to_camera_shm_ns
        return -1

    @computed_field
    @property
    def during_copy_from_camera_shm_ns(self) -> int:
        """Time spent copying from the camera shared memory buffer."""
        if self.timestamps.post_retrieve_from_camera_shm_ns and self.timestamps.pre_retrieve_from_camera_shm_ns:
            return self.timestamps.post_retrieve_from_camera_shm_ns - self.timestamps.pre_retrieve_from_camera_shm_ns
        return -1

    @computed_field
    @property
    def idle_before_copy_to_multiframe_shm_ns(self) -> int:
        """Time between retrieving from camera shared memory and copying to multi-frame shared memory."""
        if self.timestamps.pre_copy_to_multiframe_shm_ns and self.timestamps.post_retrieve_from_camera_shm_ns:
            return self.timestamps.pre_copy_to_multiframe_shm_ns - self.timestamps.post_retrieve_from_camera_shm_ns
        return -1

    @computed_field
    @property
    def during_copy_from_multiframe_shm_ns(self) -> int:
        """Time spent copying from multiframe shared memory."""
        if self.timestamps.post_retrieve_from_multiframe_shm_ns and self.timestamps.pre_retrieve_from_multiframe_shm_ns:
            return self.timestamps.post_retrieve_from_multiframe_shm_ns - self.timestamps.pre_retrieve_from_multiframe_shm_ns
        return -1
    @computed_field
    @property
    def stored_in_multiframe_shm_ns(self) -> int:
        """Time spent in the multi-frame shared memory buffer."""
        if self.timestamps.post_retrieve_from_multiframe_shm_ns and self.timestamps.pre_copy_to_multiframe_shm_ns:
            return self.timestamps.post_retrieve_from_multiframe_shm_ns - self.timestamps.pre_copy_to_multiframe_shm_ns
        return -1

    @computed_field
    @property
    def total_frame_acquisition_time_ns(self) -> int:
        """Total time spent in frame acquisition (grab + retrieve)"""
        if self.timestamps.post_frame_retrieve_ns and self.timestamps.pre_frame_grab_ns:
            return self.timestamps.post_frame_retrieve_ns - self.timestamps.pre_frame_grab_ns
        return -1

    @computed_field
    @property
    def total_ipc_travel_time_ns(self) -> int:
        """Total time spent in IPC operations (after frame grab/retrieve, before exiting mf shm)"""
        if self.timestamps.post_retrieve_from_multiframe_shm_ns and self.timestamps.post_frame_retrieve_ns:
            return self.timestamps.post_retrieve_from_multiframe_shm_ns - self.timestamps.post_frame_retrieve_ns
        return -1

    @computed_field
    @property
    def total_camera_to_recorder_time_ns(self) -> int:
        """Total time spent in IPC operations (after frame grab/retrieve, before exiting mf shm)"""
        if self.timestamps.post_retrieve_from_multiframe_shm_ns and self.timestamps.timestamp_ns:
            return self.timestamps.post_retrieve_from_multiframe_shm_ns - self.timestamps.timestamp_ns
        return -1
