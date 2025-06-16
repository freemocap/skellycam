import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class FrameLifespanTimestamps(BaseModel):
    initialized_timestamp_ns: int = Field(description="Timestamp when the frame was initialized")
    pre_grab_timestamp_ns: int = Field(description="Timestamp before grabbing the frame with cv2.grab()")
    post_grab_timestamp_ns: int = Field(description="Timestamp after grabbing the frame with cv2.grab()")
    pre_retrieve_timestamp_ns: int = Field(description="Timestamp before retrieving the frame with cv2.retrieve()")
    post_retrieve_timestamp_ns: int = Field(description="Timestamp after retrieving the frame with cv2.retrieve()")
    copy_to_camera_shm_buffer_timestamp_ns: int = Field(description="Timestamp when the frame is copied to the per-camera shared memory buffer")
    copy_from_camera_shm_buffer_timestamp_ns: int = Field(description="Timestamp when the frame is copied from the per-camera shared memory buffer")
    copy_to_multi_frame_escape_shm_buffer_timestamp_ns: int = Field(description="Timestamp when the frame is copied to the multi-frame escape shared memory buffer")
    copy_from_multi_frame_escape_shm_buffer_timestamp_ns: int = Field(description="Timestamp when the frame is copied from the multi-frame escape shared memory buffer")
    start_compress_to_jpeg_timestamp_ns: int = Field(description="Timestamp when the frame starts compressing to JPEG in preparation for sending to the frontend")
    end_compress_to_jpeg_timestamp_ns: int = Field(description="Timestamp when the frame finishes compressing to JPEG in preparation for sending to the frontend")

    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            initialized_timestamp_ns= array.frame_metadata_initialized,
            pre_grab_timestamp_ns= array.pre_grab_timestamp_ns,
            post_grab_timestamp_ns= array.post_grab_timestamp_ns,
            pre_retrieve_timestamp_ns=  array.pre_retrieve_timestamp_ns,
            post_retrieve_timestamp_ns= array.post_retrieve_timestamp_ns,
            copy_to_camera_shm_buffer_timestamp_ns= array.copy_to_camera_shm_buffer_timestamp_ns,
            copy_from_camera_shm_buffer_timestamp_ns= array.copy_from_camera_shm_buffer_timestamp_ns,
            copy_to_multi_frame_escape_shm_buffer_timestamp_ns= array.copy_to_multi_frame_escape_shm_buffer_timestamp_ns,
            copy_from_multi_frame_escape_shm_buffer_timestamp_ns= array.copy_from_multi_frame_escape_shm_buffer_timestamp_ns,
            start_compress_to_jpeg_timestamp_ns= array.start_compress_to_jpeg_timestamp_ns,
            end_compress_to_jpeg_timestamp_ns= array.end_compress_to_jpeg_timestamp_ns,
        )

    def to_numpy_record_array(self) -> np.recarray:
        return np.rec.array(
            (
                self.initialized_timestamp_ns,
                self.pre_grab_timestamp_ns,
                self.post_grab_timestamp_ns,
                self.pre_retrieve_timestamp_ns,
                self.post_retrieve_timestamp_ns,
                self.copy_to_camera_shm_buffer_timestamp_ns,
                self.copy_from_camera_shm_buffer_timestamp_ns,
                self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns,
                self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns,
                self.start_compress_to_jpeg_timestamp_ns,
                self.end_compress_to_jpeg_timestamp_ns,
            ),
            dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE
        )

    @computed_field
    def time_before_grab_signal_ns(self) -> int:
        if self.initialized_timestamp_ns  and self.pre_grab_timestamp_ns:
            return self.pre_grab_timestamp_ns - self.initialized_timestamp_ns
        return -1

    @computed_field
    def time_spent_grabbing_frame_ns(self) -> int:
        if self.post_grab_timestamp_ns and self.pre_grab_timestamp_ns:
            return self.post_grab_timestamp_ns - self.pre_grab_timestamp_ns
        return -1

    @computed_field
    def time_waiting_to_retrieve_ns(self) -> int:
        if self.pre_retrieve_timestamp_ns and self.post_grab_timestamp_ns:
            return self.pre_retrieve_timestamp_ns - self.post_grab_timestamp_ns
        return -1

    @computed_field
    def time_spent_retrieving_ns(self) -> int:
        if self.post_retrieve_timestamp_ns and self.pre_retrieve_timestamp_ns:
            return self.post_retrieve_timestamp_ns - self.pre_retrieve_timestamp_ns
        return -1

    @computed_field
    def time_spent_waiting_to_be_put_into_camera_shm_buffer_ns(self) -> int:
        if self.copy_to_camera_shm_buffer_timestamp_ns and self.post_retrieve_timestamp_ns:
            return self.copy_to_camera_shm_buffer_timestamp_ns - self.post_retrieve_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_camera_shm_buffer_ns(self) -> int:
        if self.copy_from_camera_shm_buffer_timestamp_ns and self.copy_to_camera_shm_buffer_timestamp_ns:
            return self.copy_from_camera_shm_buffer_timestamp_ns - self.copy_to_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_waiting_to_be_put_into_multi_frame_escape_shm_buffer_ns(self) -> int:
        if self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns and self.copy_from_camera_shm_buffer_timestamp_ns:
            return self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns - self.copy_from_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_multi_frame_escape_shm_buffer_ns(self) -> int:
        if self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns and self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns:
            return self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns - self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_waiting_to_start_compress_to_jpeg_ns(self) -> int:
        if self.start_compress_to_jpeg_timestamp_ns and self.copy_from_camera_shm_buffer_timestamp_ns:
            return self.start_compress_to_jpeg_timestamp_ns - self.copy_from_camera_shm_buffer_timestamp_ns
        return -1

    @computed_field
    def time_spent_in_compress_to_jpeg_ns(self) -> int:
        if self.end_compress_to_jpeg_timestamp_ns and self.start_compress_to_jpeg_timestamp_ns:
            return self.end_compress_to_jpeg_timestamp_ns - self.start_compress_to_jpeg_timestamp_ns
        return -1
