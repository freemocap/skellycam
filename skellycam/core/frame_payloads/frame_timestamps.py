import numpy as np
from pydantic import BaseModel, Field, computed_field

from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class FrameLifespanTimestamps(BaseModel):
    initialized_timestamp_ns: int = Field(description="Timestamp when the frame was initialized")
    pre_grab_timestamp_ns: int = Field(description="Timestamp before grabbing the frame with cv2.grab()")
    post_grab_timestamp_ns: int = Field(description="Timestamp after grabbing the frame with cv2.grab()")
    pre_retrieve_timestamp_ns: int = Field(description="Timestamp before retrieving the frame with cv2.retrieve()")
    post_retrieve_timestamp_ns: int = Field(description="Timestamp after retrieving the frame with cv2.retrieve()")
    copy_to_camera_shm_buffer_timestamp_ns: int = Field(description="Copied to the per-camera shared memory buffer")
    copy_from_camera_shm_buffer_timestamp_ns: int = Field(description="Copied from the per-camera shared memory buffer")
    put_into_multi_frame_payload: int = Field(description="Put into the multi-frame payload")
    copy_to_multi_frame_escape_shm_buffer_timestamp_ns: int = Field(description="Copied to the multi-frame escape shared memory buffer")
    copy_from_multi_frame_escape_shm_buffer_timestamp_ns: int = Field(description="Copied from the multi-frame escape shared memory buffer")
    start_compress_to_jpeg_timestamp_ns: int = Field(description="JPEG compression started")
    end_compress_to_jpeg_timestamp_ns: int = Field(description="JPEG compression ended")
    start_annotation_timestamp_ns: int = Field(description="Image annotation started")
    end_annotation_timestamp_ns: int = Field(description="Image annotation ended")
    @classmethod
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != FRAME_LIFECYCLE_TIMESTAMPS_DTYPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_LIFECYCLE_TIMESTAMPS_DTYPE}, "
                             f"Actual: {array.dtype}")
        return cls(
            initialized_timestamp_ns=array.frame_metadata_initialized,
            pre_grab_timestamp_ns=array.pre_grab_timestamp_ns,
            post_grab_timestamp_ns=array.post_grab_timestamp_ns,
            pre_retrieve_timestamp_ns=array.pre_retrieve_timestamp_ns,
            post_retrieve_timestamp_ns=array.post_retrieve_timestamp_ns,
            copy_to_camera_shm_buffer_timestamp_ns=array.copy_to_camera_shm_buffer_timestamp_ns,
            copy_from_camera_shm_buffer_timestamp_ns=array.copy_from_camera_shm_buffer_timestamp_ns,
            put_into_multi_frame_payload=array.put_into_multi_frame_payload,
            copy_to_multi_frame_escape_shm_buffer_timestamp_ns=array.copy_to_multi_frame_escape_shm_buffer_timestamp_ns,
            copy_from_multi_frame_escape_shm_buffer_timestamp_ns=array.copy_from_multi_frame_escape_shm_buffer_timestamp_ns,
            start_compress_to_jpeg_timestamp_ns=array.start_compress_to_jpeg_timestamp_ns,
            end_compress_to_jpeg_timestamp_ns=array.end_compress_to_jpeg_timestamp_ns,
            start_annotation_timestamp_ns=array.start_image_annotation_timestamp_ns,
            end_annotation_timestamp_ns=array.end_image_annotation_timestamp_ns,

        )

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FrameLifespanTimestamps to a numpy record array.
        """
        # Create a record array with the correct shape (1,)
        result = np.recarray(1, dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

        # Assign values to the record array
        result.frame_metadata_initialized[0] = self.initialized_timestamp_ns
        result.pre_grab_timestamp_ns[0] = self.pre_grab_timestamp_ns
        result.post_grab_timestamp_ns[0] = self.post_grab_timestamp_ns
        result.pre_retrieve_timestamp_ns[0] = self.pre_retrieve_timestamp_ns
        result.post_retrieve_timestamp_ns[0] = self.post_retrieve_timestamp_ns
        result.copy_to_camera_shm_buffer_timestamp_ns[0] = self.copy_to_camera_shm_buffer_timestamp_ns
        result.copy_from_camera_shm_buffer_timestamp_ns[0] = self.copy_from_camera_shm_buffer_timestamp_ns
        result.put_into_multi_frame_payload[0] = self.put_into_multi_frame_payload
        result.copy_to_multi_frame_escape_shm_buffer_timestamp_ns[
            0] = self.copy_to_multi_frame_escape_shm_buffer_timestamp_ns
        result.copy_from_multi_frame_escape_shm_buffer_timestamp_ns[
            0] = self.copy_from_multi_frame_escape_shm_buffer_timestamp_ns
        result.start_compress_to_jpeg_timestamp_ns[0] = self.start_compress_to_jpeg_timestamp_ns
        result.end_compress_to_jpeg_timestamp_ns[0] = self.end_compress_to_jpeg_timestamp_ns
        result.start_image_annotation_timestamp_ns[0] = self.start_annotation_timestamp_ns
        result.end_image_annotation_timestamp_ns[0] = self.end_annotation_timestamp_ns

        return result

    @computed_field
    def time_before_grab_signal_ns(self) -> int:
        if self.initialized_timestamp_ns and self.pre_grab_timestamp_ns:
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
