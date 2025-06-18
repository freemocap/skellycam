import time

import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class FrameLifespanTimestamps(BaseModel):
    timebase_mapping:TimebaseMapping
    frame_initialized_ns: int = Field(default_factory=time.perf_counter_ns,
                                      description="Timestamp when the frame was initialized")
    pre_grab_ns: int = Field(default=0, description="Timestamp before grabbing the frame with cv2.grab()")
    post_grab_ns: int = Field(default=0, description="Timestamp after grabbing the frame with cv2.grab()")
    pre_retrieve_ns: int = Field(default=0, description="Timestamp before retrieving the frame with cv2.retrieve()")
    post_retrieve_ns: int = Field(default=0, description="Timestamp after retrieving the frame with cv2.retrieve()")
    copy_to_camera_shm_ns: int = Field(default=0, description="Copied to the per-camera shared memory buffer")
    retrieve_from_camera_shm_ns: int = Field(default=0,
                                             description="Retrieved from the per-camera shared memory buffer")
    copy_to_multiframe_shm_ns: int = Field(default=0,
                                           description="Copied to the multi-frame escape shared memory buffer")
    retrieve_from_multiframe_shm_ns: int = Field(default=0,
                                                 description="Retrieved from the multi-frame escape shared memory buffer")
    @computed_field
    @property
    def timestamp_local_unix_ms(self) -> float:
        """
        Using the midpoint between pre and post grab timestamps to represent the frame's timestamp.
        """
        if self.pre_grab_ns is None or self.post_grab_ns is None:
            raise ValueError("pre_retrieve_ns and post_grab_ns cannot be None")
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns((self.post_grab_ns - self.pre_grab_ns) // 2, local_time=True) / 1_000_000

    @computed_field
    @property
    def frame_initialized_local_unix_ms(self) -> float:
        """
        Convert the frame initialized timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.frame_initialized_ns, local_time=True) / 1_000_000

    @computed_field
    @property
    def pre_grab_local_unix_ms(self) -> float:
        """
        Convert the pre-grab timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.pre_grab_ns, local_time=True) / 1_000_000
    @computed_field
    @property
    def post_grab_local_unix_ms(self) -> float:
        """
        Convert the post-grab timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.post_grab_ns, local_time=True) / 1_000_000

    @computed_field
    @property
    def pre_retrieve_local_unix_ms(self) -> float:
        """
        Convert the pre-retrieve timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.pre_retrieve_ns, local_time=True) / 1_000_000

    @computed_field
    @property
    def post_retrieve_local_unix_ms(self) -> float:
        """
        Convert the post-retrieve timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.post_retrieve_ns, local_time=True) / 1_000_000
    @computed_field
    @property
    def copy_to_camera_shm_local_unix_ms(self) -> float:
        """
        Convert the copy to camera shared memory timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.copy_to_camera_shm_ns, local_time=True) / 1_000_000

    @computed_field
    @property
    def retrieve_from_camera_shm_local_unix_ms(self) -> float:
        """
        Convert the retrieve from camera shared memory timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.retrieve_from_camera_shm_ns, local_time=True) / 1_000_000
    @computed_field
    @property
    def copy_to_multiframe_shm_local_unix_ms(self) -> float:
        """
        Convert the copy to multi-frame shared memory timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.copy_to_multiframe_shm_ns, local_time=True) / 1_000_000
    @computed_field
    @property
    def retrieve_from_multiframe_shm_local_unix_ms(self) -> float:
        """
        Convert the retrieve from multi-frame shared memory timestamp to local Unix time in milliseconds.
        """
        return self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(self.retrieve_from_multiframe_shm_ns, local_time=True) / 1_000_000


    # Durations
    @computed_field
    @property
    def idle_before_grab_duration_ms(self) -> float:
        if self.frame_initialized_ns and self.pre_grab_ns:
            return (self.pre_grab_ns - self.frame_initialized_ns)/1_000_000
        return -1

    @computed_field
    @property
    def frame_grab_duration_ms(self) -> float:
        if self.post_grab_ns and self.pre_grab_ns:
            return (self.post_grab_ns - self.pre_grab_ns)/1_000_000
        return -1

    @computed_field
    @property
    def idle_before_retrieve_duration_ms(self) -> float:
        if self.pre_retrieve_ns and self.post_grab_ns:
            return (self.pre_retrieve_ns - self.post_grab_ns)/1_000_000
        return -1

    @computed_field
    @property
    def frame_retrieve_duration_ms(self) -> float:
        if self.post_retrieve_ns and self.pre_retrieve_ns:
            return (self.post_retrieve_ns - self.pre_retrieve_ns)/1_000_000
        return -1


    @computed_field
    @property
    def idle_before_copy_to_camera_shm_duration_ms(self) -> float:
        if self.copy_to_camera_shm_ns and self.post_retrieve_ns:
            return (self.copy_to_camera_shm_ns - self.post_retrieve_ns)/1_000_000
        return -1

    @computed_field
    @property
    def idle_in_camera_shm_duration_ms(self) -> float:
        if self.retrieve_from_camera_shm_ns and self.copy_to_camera_shm_ns:
            return (self.retrieve_from_camera_shm_ns - self.copy_to_camera_shm_ns)/1_000_000
        return -1


    @computed_field    # Individual timing metrics - Multi-Frame Operations
    @property
    def idle_before_copy_to_multiframe_shm_duration_ms(self) -> float:
        if self.copy_to_multiframe_shm_ns and self.retrieve_from_camera_shm_ns:
            return (self.copy_to_multiframe_shm_ns - self.retrieve_from_camera_shm_ns)/1_000_000
        return -1

    @computed_field
    @property
    def idle_in_multiframe_shm_duration_ms(self) -> float:
        if self.retrieve_from_multiframe_shm_ns and self.copy_to_multiframe_shm_ns:
            return (self.retrieve_from_multiframe_shm_ns - self.copy_to_multiframe_shm_ns)/1_000_000
        return -1


    @computed_field    # Higher-level category timing metrics
    @property
    def total_frame_acquisition_duration_ms(self) -> float:
        """Total time spent in frame acquisition (grab + retrieve)"""
        if self.post_retrieve_ns and self.pre_grab_ns:
            return (self.post_retrieve_ns - self.pre_grab_ns)/1_000_000
        return -1

    @computed_field
    @property
    def total_ipc_travel_duration_ms(self) -> float:
        """Total time spent in IPC operations (after frame grab/retrieve, before exiting mf shm"""
        if self.retrieve_from_multiframe_shm_ns and self.post_retrieve_ns:
            return (self.retrieve_from_multiframe_shm_ns - self.post_retrieve_ns)/1_000_000
        return -1
    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            frame_initialized_ns=array.frame_initialized_ns,
            pre_grab_ns=array.pre_grab_ns,
            post_grab_ns=array.post_grab_ns,
            pre_retrieve_ns=array.pre_retrieve_ns,
            post_retrieve_ns=array.post_retrieve_ns,
            copy_to_camera_shm_ns=array.copy_to_camera_shm_ns,
            retrieve_from_camera_shm_ns=array.retrieve_from_camera_shm_ns,
            copy_to_multiframe_shm_ns=array.copy_to_multiframe_shm_ns,
            retrieve_from_multiframe_shm_ns=array.retrieve_from_multiframe_shm_ns,
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
        result.pre_grab_ns[0] = self.pre_grab_ns
        result.post_grab_ns[0] = self.post_grab_ns
        result.pre_retrieve_ns[0] = self.pre_retrieve_ns
        result.post_retrieve_ns[0] = self.post_retrieve_ns
        result.copy_to_camera_shm_ns[0] = self.copy_to_camera_shm_ns
        result.retrieve_from_camera_shm_ns[0] = self.retrieve_from_camera_shm_ns
        result.copy_to_multiframe_shm_ns[0] = self.copy_to_multiframe_shm_ns
        result.retrieve_from_multiframe_shm_ns[0] = self.retrieve_from_multiframe_shm_ns

        return result



if __name__ == "__main__":
    # Example usage
    timestamps = FrameLifespanTimestamps(
        timebase_mapping=TimebaseMapping()
    )
    print(timestamps.to_numpy_record_array())
    print(timestamps.idle_before_grab_duration_ms)
    print(timestamps.frame_grab_duration_ms)
    print(timestamps.idle_before_retrieve_duration_ms)
    print(timestamps.frame_retrieve_duration_ms)
    print(timestamps.total_frame_acquisition_duration_ms)





