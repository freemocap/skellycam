import time
from enum import Enum

import numpy as np


class FRAME_METADATA_MODEL(Enum):
    """
    An enum to represent the metadata associated with a frame of image data.
    The value of each enum member corresponds to the index of that value in the metadata np.ndarray.
    We will store the metadata in an numpy array while we're doing the shared memory nonsense, and convert to a Pydantic model when we're safely away from Camera land.
    """
    CAMERA_ID: int = 0  # CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)
    FRAME_NUMBER: int = 1  # (The number of frames that have been captured by the camera since it was started)
    INITIALIZED: int = 2  # (timestamp when the metadata was initialized)
    PRE_GRAB_TIMESTAMP_NS: int = 3  # (timestamp before calling cv2.VideoCapture.grab())
    POST_GRAB_TIMESTAMP_NS: int = 4  # (timestamp after calling cv2.VideoCapture.grab())
    PRE_RETRIEVE_TIMESTAMP_NS: int = 5  # (timestamp before calling cv2.VideoCapture.retrieve())
    POST_RETRIEVE_TIMESTAMP_NS: int = 6  # (timestamp after calling cv2.VideoCapture.retrieve())
    COPY_TO_BUFFER_TIMESTAMP_NS: int = 7  # (timestamp when frame was copied to shared memory)
    COPY_FROM_BUFFER_TIMESTAMP_NS: int = 8  # (timestamp when frame was copied from shared memory)
    START_COMPRESS_TO_JPEG_TIMESTAMP_NS: int = 9  # (timestamp before compressing to jpeg)
    END_COMPRESS_TO_JPEG_TIMESTAMP_NS: int = 10  # (timestamp_ns (timestamp after compressing to jpeg)
    START_IMAGE_ANNOTATION_TIMESTAMP_NS: int = 11  # (timestamp before annotating image)
    END_IMAGE_ANNOTATION_TIMESTAMP_NS: int = 12  # (timestamp after annotating image)


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


if __name__ == "__main__":
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
