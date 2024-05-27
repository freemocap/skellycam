import time
from enum import Enum

import numpy as np


class FRAME_METADATA_MODEL(Enum):
    """
    An enum to represent the metadata associated with a frame of image data.
    The value of each enum member corresponds to the index of that value in the metadata np.ndarray.
    """
    CAMERA_ID: int = 0  # CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)
    FRAME_NUMBER: int = 1  # frame_number (The number of frames that have been captured by the camera since it was started)
    TIMESTAMP_NS: int = 2  # timestamp_ns (mean of pre- and post- grab timestamps)
    PRE_GRAB_TIMESTAMP_NS: int = 3  # pre_grab_timestamp_ns (timestamp before calling cv2.VideoCapture.grab())
    POST_GRAB_TIMESTAMP_NS: int = 4  # post_grab_timestamp_ns (timestamp after calling cv2.VideoCapture.grab())
    PRE_RETRIEVE_TIMESTAMP_NS: int = 5  # pre_retrieve_timestamp_ns (timestamp before calling cv2.VideoCapture.retrieve())
    POST_RETRIEVE_TIMESTAMP_NS: int = 6  # post_retrieve_timestamp_ns (timestamp after calling cv2.VideoCapture.retrieve())
    COPY_TO_BUFFER_TIMESTAMP_NS: int = 7  # copy_timestamp_ns (timestamp when frame was copied to shared memory)
    COPY_FROM_BUFFER_TIMESTAMP_NS: int = 8  # copy_timestamp_ns (timestamp when frame was copied from shared memory


FRAME_METADATA_DTYPE = np.uint64
FRAME_METADATA_SHAPE = (len(FRAME_METADATA_MODEL),)
FRAME_METADATA_SIZE_BYTES = np.dtype(FRAME_METADATA_DTYPE).itemsize * np.prod(FRAME_METADATA_SHAPE)


def create_empty_frame_metadata(
        camera_id: int,
        frame_number: int
) -> np.ndarray:
    metadata_array = np.nan * np.empty(FRAME_METADATA_SHAPE, dtype=FRAME_METADATA_DTYPE)
    metadata_array[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_id
    metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value] = frame_number
    return metadata_array


if __name__ == "__main__":
    print(FRAME_METADATA_MODEL)
    print(FRAME_METADATA_DTYPE)
    print(FRAME_METADATA_SHAPE)
    print(FRAME_METADATA_SIZE_BYTES)
    empty_metadata = create_empty_frame_metadata(1, 1)
    print(empty_metadata)
    empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()
    print(empty_metadata)
