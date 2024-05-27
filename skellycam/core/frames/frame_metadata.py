from enum import Enum, auto

import numpy as np


class FRAME_METADATA_MODEL(Enum):
    """
    An enum to represent the metadata associated with a frame of image data.
    The index of each enum member corresponds to the index of that value in the metadata np.ndarray.
    """
    CAMERA_ID = auto()  # CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)
    FRAME_NUMBER = auto()  # frame_number (The number of frames that have been captured by the camera since it was started)
    TIMESTAMP_NS = auto()  # timestamp_ns (mean of pre- and post- grab timestamps)
    PRE_GRAB_TIMESTAMP_NS = auto()  # pre_grab_timestamp_ns (timestamp before calling cv2.VideoCapture.grab())
    POST_GRAB_TIMESTAMP_NS = auto()  # post_grab_timestamp_ns (timestamp after calling cv2.VideoCapture.grab())
    PRE_RETRIEVE_TIMESTAMP_NS = auto()  # pre_retrieve_timestamp_ns (timestamp before calling cv2.VideoCapture.retrieve())
    POST_RETRIEVE_TIMESTAMP_NS = auto()  # post_retrieve_timestamp_ns (timestamp after calling cv2.VideoCapture.retrieve())
    COPY_TO_BUFFER_TIMESTAMP_NS = auto()  # copy_timestamp_ns (timestamp when frame was copied to shared memory)
    COPY_FROM_BUFFER_TIMESTAMP_NS = auto()  # copy_timestamp_ns (timestamp when frame was copied from shared memory


FRAME_METADATA_DTYPE = np.uint64
FRAME_METADATA_SHAPE = (len(FRAME_METADATA_MODEL),)
FRAME_METADATA_SIZE_BYTES = np.dtype(FRAME_METADATA_DTYPE).itemsize * np.prod(FRAME_METADATA_SHAPE)

if __name__ == "__main__":
    print(FRAME_METADATA_MODEL)
    print(FRAME_METADATA_DTYPE)
    print(FRAME_METADATA_SHAPE)
    print(FRAME_METADATA_SIZE_BYTES)
