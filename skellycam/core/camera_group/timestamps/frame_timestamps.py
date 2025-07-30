import logging
import time
from dataclasses import dataclass
from functools import cached_property

import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE, FRAME_METADATA_DTYPE

logger = logging.getLogger(__name__)

@dataclass
class FrameTimestamps:
    timebase_mapping:TimebaseMapping
    frame_initialized_ns: int = 0
    pre_frame_grab_ns: int = 0
    post_frame_grab_ns: int = 0
    pre_frame_retrieve_ns: int = 0
    post_frame_retrieve_ns: int = 0
    pre_copy_to_camera_shm_ns: int = 0
    post_copy_to_camera_shm_ns: int = 0
    pre_frame_record_ns: int = 0
    post_frame_record_ns: int = 0


    @property
    def timestamp_ns(self) -> int:
        """
        Using the midpoint between pre and post grab timestamps to represent the frame's timestamp.
        """
        if not self.pre_frame_grab_ns or not self.post_frame_grab_ns:
            raise ValueError("pre_frame_retrieve_ns and post_frame_grab_ns cannot be None")
        return (self.post_frame_grab_ns + self.pre_frame_grab_ns) // 2


    @cached_property
    def durations(self) -> 'FrameDurations':
        """
        Get a helper object that calculates various duration metrics.
        """
        return FrameDurations(timestamps=self)

    @classmethod
    def from_frame_timestamps_recarray(cls, timestamps: np.recarray):
        if timestamps.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"\nExpected:\n\t {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"\nReceived: \n\t {timestamps.dtype}")
        return cls(
            frame_initialized_ns=timestamps.frame_initialized_ns[0],
            pre_frame_grab_ns=timestamps.pre_frame_grab_ns[0],
            post_frame_grab_ns=timestamps.post_frame_grab_ns[0],
            pre_frame_retrieve_ns=timestamps.pre_frame_retrieve_ns[0],
            post_frame_retrieve_ns=timestamps.post_frame_retrieve_ns[0],
            pre_copy_to_camera_shm_ns=timestamps.pre_copy_to_camera_shm_ns[0],
            post_copy_to_camera_shm_ns=timestamps.post_copy_to_camera_shm_ns[0],
            pre_frame_record_ns=timestamps.pre_frame_record_ns[0],
            post_frame_record_ns=timestamps.post_frame_record_ns[0],

            timebase_mapping=TimebaseMapping.from_numpy_record_array(timestamps.timebase_mapping)
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
        result.post_copy_to_camera_shm_ns[0] = self.post_copy_to_camera_shm_ns
        result.pre_frame_record_ns[0] = self.pre_frame_record_ns
        result.post_frame_record_ns[0] = self.post_frame_record_ns

        return result


@dataclass
class FrameDurations:
    """
    Helper class for FrameTimestamps that calculates various duration metrics
    between different timestamp points in the frame lifecycle.
    """
    timestamps: FrameTimestamps


    @cached_property
    def during_frame_grab_ns(self) -> int:
        """Time spent in the grab operation."""
        if self.timestamps.post_frame_grab_ns and self.timestamps.pre_frame_grab_ns:
            return self.timestamps.post_frame_grab_ns - self.timestamps.pre_frame_grab_ns
        return -1

    @cached_property
    def idle_before_retrieve_ns(self)-> int:
        if self.timestamps.pre_frame_retrieve_ns and self.timestamps.post_frame_grab_ns:
            return self.timestamps.pre_frame_retrieve_ns - self.timestamps.post_frame_grab_ns
        return -1

    @cached_property
    def during_frame_retrieve_ns(self) -> int:
        """Time spent in the retrieve operation."""
        if self.timestamps.post_frame_retrieve_ns and self.timestamps.pre_frame_retrieve_ns:
            return self.timestamps.post_frame_retrieve_ns - self.timestamps.pre_frame_retrieve_ns
        return -1

    @cached_property
    def idle_before_copy_to_camera_shm_ns(self) -> int:
        """Time between frame retrieval and copying to camera shared memory."""
        if self.timestamps.post_frame_retrieve_ns and self.timestamps.pre_copy_to_camera_shm_ns:
            return self.timestamps.pre_copy_to_camera_shm_ns - self.timestamps.post_frame_retrieve_ns
        return -1

    @cached_property
    def during_copy_to_camera_shm_ns(self) -> int:
        """Time spent copying the frame to camera shared memory."""
        if self.timestamps.post_copy_to_camera_shm_ns and self.timestamps.pre_copy_to_camera_shm_ns:
            return self.timestamps.post_copy_to_camera_shm_ns - self.timestamps.pre_copy_to_camera_shm_ns
        return -1

    @cached_property
    def idle_before_frame_record_ns(self) -> int:
        """Time between frame retrieval and copying to camera shared memory."""
        if self.timestamps.pre_frame_record_ns and self.timestamps.post_copy_to_camera_shm_ns:
            return self.timestamps.pre_frame_record_ns  - self.timestamps.post_copy_to_camera_shm_ns
        return -1

    @cached_property
    def during_frame_record_ns(self) -> int:
        """Time between frame retrieval and copying to camera shared memory."""
        if self.timestamps.post_frame_record_ns and self.timestamps.pre_frame_record_ns:
            return self.timestamps.post_frame_record_ns - self.timestamps.pre_frame_record_ns
        return -1



    @cached_property
    def total_frame_processing_time_ns(self) -> int:
        """Total time spent in frame acquisition (grab + retrieve)"""
        if self.timestamps.post_frame_record_ns and self.timestamps.pre_frame_grab_ns:
            return self.timestamps.post_frame_record_ns - self.timestamps.pre_frame_grab_ns
        return -1

    @cached_property
    def total_camera_idle_time_ns(self) -> int:
        """Time between frame initialization and the start of the grab operation."""
        if self.timestamps.frame_initialized_ns and self.timestamps.pre_frame_grab_ns:
            return self.timestamps.pre_frame_grab_ns - self.timestamps.frame_initialized_ns
        return -1

    def __str__(self):
        return (f"\tduring_frame_grab (ms):              {self.during_frame_grab_ns/1e6},\n "
                f"\tidle_before_retrieve (ms):           {self.idle_before_retrieve_ns/1e6},\n "
                f"\tduring_frame_retrieve (ms):          {self.during_frame_retrieve_ns/1e6},\n "
                f"\tidle_before_copy_to_camera_shm (ms): {self.idle_before_copy_to_camera_shm_ns/1e6},\n "
                f"\tduring_copy_to_camera_shm (ms):      {self.during_copy_to_camera_shm_ns/1e6},\n "
                f"\tidle_before_frame_record (ms):       {self.idle_before_frame_record_ns/1e6},\n "
                f"\tduring_frame_record (ms):            {self.during_frame_record_ns/1e6},\n "
                f"\ttotal_frame_processing_time (ms):    { self.total_frame_processing_time_ns/1e6},\n "
                f"\ttotal_camera_idle_time (ms):         {self.total_camera_idle_time_ns/1e6}\n--------------------------------\n ")