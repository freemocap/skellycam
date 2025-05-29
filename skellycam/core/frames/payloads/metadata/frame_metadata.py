import numpy as np
from pydantic import BaseModel, computed_field
from pydantic import Field

from skellycam.core.types import CameraIndex
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_SHAPE


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
    def from_frame_metadata(cls, frame_metadata: np.ndarray):
        return cls(
            initialized_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.FRAME_METADATA_INITIALIZED.value],
            pre_grab_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.PRE_GRAB_TIMESTAMP_NS.value],
            post_grab_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value],
            pre_retrieve_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value],
            post_retrieve_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.POST_RETRIEVE_TIMESTAMP_NS.value],
            copy_to_camera_shm_buffer_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.COPY_TO_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value],
            copy_from_camera_shm_buffer_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.COPY_FROM_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value],
            copy_to_multi_frame_escape_shm_buffer_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.COPY_TO_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value],
            copy_from_multi_frame_escape_shm_buffer_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.COPY_FROM_CAMERA_SHM_BUFFER_TIMESTAMP_NS.value],
            start_compress_to_jpeg_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.START_COMPRESS_TO_JPEG_TIMESTAMP_NS.value],
            end_compress_to_jpeg_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.END_COMPRESS_TO_JPEG_TIMESTAMP_NS.value],
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


class FrameMetadata(BaseModel):
    """
    A Pydantic model to represent the metadata associated with a frame of image data, we will build this from the numpy array once we've cleared the camera/shm whackiness.
    """
    camera_id: CameraIndex = CameraIndex(0)
    frame_number: int = 0
    frame_lifespan_timestamps: FrameLifespanTimestamps

    @property
    def timestamp_ns(self) -> int:
        return self.frame_lifespan_timestamps.post_grab_timestamp_ns

    @classmethod
    def from_frame_metadata_array(cls, metadata_array: np.ndarray):
        if metadata_array.shape != FRAME_METADATA_SHAPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_METADATA_SHAPE}, "
                             f"Actual: {metadata_array.shape}")
        return cls(
            camera_id=metadata_array[FRAME_METADATA_MODEL.CAMERA_INDEX.value],
            frame_number=metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value],
            frame_lifespan_timestamps=FrameLifespanTimestamps.from_frame_metadata(metadata_array)
        )

