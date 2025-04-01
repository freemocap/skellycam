import numpy as np
from pydantic import BaseModel, computed_field

from skellycam.core import CameraIndex
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, \
    FRAME_METADATA_SHAPE


class FrameLifespanTimestamps(BaseModel):
    initialized_timestamp_ns: int
    pre_grab_timestamp_ns: int
    post_grab_timestamp_ns: int
    pre_retrieve_timestamp_ns: int
    post_retrieve_timestamp_ns: int
    copy_to_buffer_timestamp_ns: int
    copy_from_buffer_timestamp_ns: int
    start_annotate_image_timestamp_ns: int
    end_annotate_image_timestamp_ns: int
    start_compress_to_jpeg_timestamp_ns: int
    end_compress_to_jpeg_timestamp_ns: int

    @classmethod
    def from_frame_metadata(cls, frame_metadata: np.ndarray):
        return cls(
            initialized_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.FRAME_METADATA_INITIALIZED.value],
            pre_grab_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.PRE_GRAB_TIMESTAMP_NS.value],
            post_grab_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value],
            pre_retrieve_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value],
            post_retrieve_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.POST_RETRIEVE_TIMESTAMP_NS.value],
            copy_to_buffer_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value],
            copy_from_buffer_timestamp_ns=frame_metadata[FRAME_METADATA_MODEL.COPY_FROM_BUFFER_TIMESTAMP_NS.value],
            start_annotate_image_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.START_IMAGE_ANNOTATION_TIMESTAMP_NS.value],
            end_annotate_image_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.END_IMAGE_ANNOTATION_TIMESTAMP_NS.value],
            start_compress_to_jpeg_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.START_COMPRESS_TO_JPEG_TIMESTAMP_NS.value],
            end_compress_to_jpeg_timestamp_ns=frame_metadata[
                FRAME_METADATA_MODEL.END_COMPRESS_TO_JPEG_TIMESTAMP_NS.value],
        )

    @computed_field
    def total_time_ns(self) -> int:
        return self.end_compress_to_jpeg_timestamp_ns - self.initialized_timestamp_ns

    @computed_field
    def time_before_grab_ns(self) -> int:
        return self.pre_grab_timestamp_ns - self.initialized_timestamp_ns

    @computed_field
    def time_spent_grabbing_ns(self) -> int:
        return self.post_grab_timestamp_ns - self.pre_grab_timestamp_ns

    @computed_field
    def time_waiting_to_retrieve_ns(self) -> int:
        return self.pre_retrieve_timestamp_ns - self.post_grab_timestamp_ns

    @computed_field
    def time_spent_retrieving_ns(self) -> int:
        return self.post_retrieve_timestamp_ns - self.pre_retrieve_timestamp_ns

    @computed_field
    def time_spent_waiting_to_be_put_into_buffer_ns(self) -> int:
        return self.copy_to_buffer_timestamp_ns - self.post_retrieve_timestamp_ns

    @computed_field
    def time_spent_in_buffer_ns(self) -> int:
        return self.copy_from_buffer_timestamp_ns - self.copy_to_buffer_timestamp_ns

    @computed_field
    def time_spent_waiting_to_start_annotate_image_ns(self) -> int:
        return self.start_annotate_image_timestamp_ns - self.copy_from_buffer_timestamp_ns

    @computed_field
    def time_spent_in_annotate_image_ns(self) -> int:
        return self.end_annotate_image_timestamp_ns - self.start_annotate_image_timestamp_ns

    @computed_field
    def time_spent_waiting_to_start_compress_to_jpeg_ns(self) -> int:
        return self.start_compress_to_jpeg_timestamp_ns - self.copy_from_buffer_timestamp_ns

    @computed_field
    def time_spent_in_compress_to_jpeg_ns(self) -> int:
        return self.end_compress_to_jpeg_timestamp_ns - self.start_compress_to_jpeg_timestamp_ns


class FrameMetadata(BaseModel):
    """
    A Pydantic model to represent the metadata associated with a frame of image data, we will build this from the numpy array once we've cleared the camera/shm whackiness.
    """
    camera_id: int = CameraIndex(0)
    frame_number: int = 0
    frame_lifespan_timestamps_ns: FrameLifespanTimestamps

    @property
    def timestamp_ns(self) -> int:
        return self.frame_lifespan_timestamps_ns.post_grab_timestamp_ns

    @classmethod
    def from_frame_metadata_array(cls, metadata_array: np.ndarray):
        if metadata_array.shape != FRAME_METADATA_SHAPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_METADATA_SHAPE}, "
                             f"Actual: {metadata_array.shape}")
        return cls(
            camera_id=metadata_array[FRAME_METADATA_MODEL.CAMERA_INDEX.value],
            frame_number=metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value],
            frame_lifespan_timestamps_ns=FrameLifespanTimestamps.from_frame_metadata(metadata_array)
        )

    def to_df_row(self):
        lifespan_dict = {f"camera_{self.camera_id}_{key}": value for key, value in
                         self.frame_lifespan_timestamps_ns.model_dump().items()}
        return {
            f"camera_{self.camera_id}_frame_number": self.frame_number,
            f"camera_{self.camera_id}_timestamp_ns": self.timestamp_ns,
            **lifespan_dict
        }
