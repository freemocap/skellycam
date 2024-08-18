import time
from enum import Enum
from pprint import pprint, pformat

import numpy as np
from pydantic import BaseModel, computed_field

from skellycam.core import CameraId


class FRAME_METADATA_MODEL(Enum):
    """
    An enum to represent the metadata associated with a frame of image data.
    The value of each enum member corresponds to the index of that value in the metadata np.ndarray.
    We will store the metadata in an numpy array while we're doing the shared memory nonsense, and convert to a Pydantic model when we're safely away from Camera land.
    """
    CAMERA_ID: int = 0  # CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)
    FRAME_NUMBER: int = 1  # frame_number (The number of frames that have been captured by the camera since it was started)
    INITIALIZED: int = 2  # initialized (timestamp when the metadata was initialized)
    PRE_GRAB_TIMESTAMP_NS: int = 3  # pre_grab_timestamp_ns (timestamp before calling cv2.VideoCapture.grab())
    POST_GRAB_TIMESTAMP_NS: int = 4  # post_grab_timestamp_ns (timestamp after calling cv2.VideoCapture.grab())
    PRE_RETRIEVE_TIMESTAMP_NS: int = 5  # pre_retrieve_timestamp_ns (timestamp before calling cv2.VideoCapture.retrieve())
    POST_RETRIEVE_TIMESTAMP_NS: int = 6  # post_retrieve_timestamp_ns (timestamp after calling cv2.VideoCapture.retrieve())
    COPY_TO_BUFFER_TIMESTAMP_NS: int = 7  # copy_timestamp_ns (timestamp when frame was copied to shared memory)
    COPY_FROM_BUFFER_TIMESTAMP_NS: int = 8  # copy_timestamp_ns (timestamp when frame was copied from shared memory
    START_CONVERT_TO_FRONTEND_PAYLOAD_TIMESTAMP_NS: int = 9  # start_convert_to_frontend_payload_timestamp_ns
    END_CONVERT_TO_FRONTEND_PAYLOAD_TIMESTAMP_NS: int = 10  # end_convert_to_frontend_payload_timestamp_ns
    START_SEND_DOWN_WEBSOCKET_TIMESTAMP_NS: int = 11  # start_send_down_websocket_timestamp_ns

FRAME_METADATA_DTYPE = np.uint64
FRAME_METADATA_SHAPE = (len(FRAME_METADATA_MODEL),)
FRAME_METADATA_SIZE_BYTES = np.dtype(FRAME_METADATA_DTYPE).itemsize * np.prod(FRAME_METADATA_SHAPE)
def create_empty_frame_metadata(
        camera_id: int,
        frame_number: int
) -> np.ndarray:
    metadata_array = np.zeros(FRAME_METADATA_SHAPE,
                              dtype=FRAME_METADATA_DTYPE)
    metadata_array[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_id
    metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value] = frame_number
    metadata_array[FRAME_METADATA_MODEL.INITIALIZED.value] = time.perf_counter_ns()

    if metadata_array.dtype != FRAME_METADATA_DTYPE:
        raise ValueError(f"Metadata array has the wrong dtype: {metadata_array.dtype}")
    return metadata_array


class FrameMetadata(BaseModel):
    """
    A Pydantic model to represent the metadata associated with a frame of image data, we will build this from the numpy array once we've cleared the camera/shm whackiness.
    """
    camera_id: int = CameraId(0)
    frame_number: int = 0

    initialized_timestamp_ns: int = time.perf_counter_ns()
    pre_grab_timestamp_ns: int = time.perf_counter_ns()
    post_grab_timestamp_ns: int = time.perf_counter_ns()
    pre_retrieve_timestamp_ns: int = time.perf_counter_ns()
    post_retrieve_timestamp_ns: int = time.perf_counter_ns()
    copy_to_buffer_timestamp_ns: int = time.perf_counter_ns()
    copy_from_buffer_timestamp_ns: int = time.perf_counter_ns()
    start_convert_to_frontend_payload_timestamp_ns: int = time.perf_counter_ns()
    end_convert_to_frontend_payload_timestamp_ns: int = time.perf_counter_ns()
    start_send_down_websocket_timestamp_ns: int = time.perf_counter_ns()

    @classmethod
    def from_array(cls, metadata_array: np.ndarray):
        if metadata_array.shape != FRAME_METADATA_SHAPE:
            raise ValueError(f"Metadata array shape mismatch - "
                             f"Expected: {FRAME_METADATA_SHAPE}, "
                             f"Actual: {metadata_array.shape}")
        return cls(
            camera_id=metadata_array[FRAME_METADATA_MODEL.CAMERA_ID.value],
            frame_number=metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value],
            initialized_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.INITIALIZED.value],
            pre_grab_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.PRE_GRAB_TIMESTAMP_NS.value],
            post_grab_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.POST_GRAB_TIMESTAMP_NS.value],
            pre_retrieve_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value],
            post_retrieve_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.POST_RETRIEVE_TIMESTAMP_NS.value],
            copy_to_buffer_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.COPY_TO_BUFFER_TIMESTAMP_NS.value],
            copy_from_buffer_timestamp_ns=metadata_array[FRAME_METADATA_MODEL.COPY_FROM_BUFFER_TIMESTAMP_NS.value],
            start_convert_to_frontend_payload_timestamp_ns=metadata_array[
                FRAME_METADATA_MODEL.START_CONVERT_TO_FRONTEND_PAYLOAD_TIMESTAMP_NS.value],
            end_convert_to_frontend_payload_timestamp_ns=metadata_array[
                FRAME_METADATA_MODEL.END_CONVERT_TO_FRONTEND_PAYLOAD_TIMESTAMP_NS.value],
            send_down_websocket_timestamp_ns=metadata_array[
                FRAME_METADATA_MODEL.START_SEND_DOWN_WEBSOCKET_TIMESTAMP_NS.value]
        )

    @computed_field
    def total_time_ns(self) -> int:
        return self.start_send_down_websocket_timestamp_ns - self.initialized_timestamp_ns

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
    def time_spent_waiting_to_start_converting_to_frontend_payload_ns(self) -> int:
        return self.start_convert_to_frontend_payload_timestamp_ns - self.copy_from_buffer_timestamp_ns

    @computed_field
    def time_spent_converting_to_frontend_payload_ns(self) -> int:
        return self.end_convert_to_frontend_payload_timestamp_ns - self.start_convert_to_frontend_payload_timestamp_ns

    @computed_field
    def time_spent_waiting_to_be_spent_down_websocket_ns(self) -> int:
        return self.start_send_down_websocket_timestamp_ns - self.end_convert_to_frontend_payload_timestamp_ns





if __name__ == "__main__":
    from pprint import pprint
    print(FRAME_METADATA_MODEL)
    print(FRAME_METADATA_DTYPE)
    print(FRAME_METADATA_SHAPE)
    print(FRAME_METADATA_SIZE_BYTES)
    empty_metadata = create_empty_frame_metadata(99, 32)
    print(f"empty_metadata: {empty_metadata}")
    print(f"empty_metadata dtype: {empty_metadata.dtype}")

    [print(f"{key}: {empty_metadata[key.value]}") for key in FRAME_METADATA_MODEL]
    empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()
    print(f"empty_metadata w/ timestamp: {empty_metadata}")
    [print(f"{key}: {empty_metadata[key.value]}") for key in FRAME_METADATA_MODEL]
    time_elapsed_ns = empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] - empty_metadata[
        FRAME_METADATA_MODEL.INITIALIZED.value]
    print(f"Time elapsed: {time_elapsed_ns} ns ({time_elapsed_ns / 1_000_000} ms, {time_elapsed_ns / 1_000_000_000} s)")

    print('\n\n-------------------\n\n--- FrameMetadata ---\n\n')
    metadata_model = FrameMetadata()
    print(pformat(metadata_model.model_dump(), indent=2, sort_dicts=False))
