import time
from enum import Enum

import numpy as np

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig


class FRAME_METADATA_MODEL(Enum):
    """
    An enum to represent the metadata associated with a frame of image data.
    The value of each enum member corresponds to the index of that value in the metadata np.ndarray.
    We will store the metadata in a numpy array while we're doing the shared memory nonsense, and
    convert to a Pydantic model when we're safely away from Camera land.
    """
    CAMERA_INDEX: int = 0  # CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)
    IMAGE_HEIGHT: int = 1  # Height of the frame in pixels
    IMAGE_WIDTH: int = 2  # Width of the frame in pixels
    IMAGE_COLOR_CHANNELS: int = 3  # Number of color channels in the image
    FRAME_NUMBER: int = 4  # (The number of frames that have been captured by the camera since it was started)
    FRAME_METADATA_INITIALIZED: int = 5  # (timestamp when the metadata was initialized)
    PRE_GRAB_TIMESTAMP_NS: int = 6  # (timestamp before calling cv2.VideoCapture.grab())
    POST_GRAB_TIMESTAMP_NS: int = 7  # (timestamp after calling cv2.VideoCapture.grab())
    PRE_RETRIEVE_TIMESTAMP_NS: int = 8  # (timestamp before calling cv2.VideoCapture.retrieve())
    POST_RETRIEVE_TIMESTAMP_NS: int = 9  # (timestamp after calling cv2.VideoCapture.retrieve())
    COPY_TO_CAMERA_SHM_BUFFER_TIMESTAMP_NS: int = 10  # (timestamp when frame was copied to shared memory)
    COPY_FROM_CAMERA_SHM_BUFFER_TIMESTAMP_NS: int = 11  # (timestamp when frame was copied from shared memory)
    COPY_TO_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS: int = 12  # (timestamp when frame was copied to multi-frame escape shared memory)
    COPY_FROM_MULTI_FRAME_ESCAPE_SHM_BUFFER_TIMESTAMP_NS: int = 13  # (timestamp when frame was copied from multi-frame escape shared memory)
    START_COMPRESS_TO_JPEG_TIMESTAMP_NS: int = 13  # (timestamp before compressing to jpeg)
    END_COMPRESS_TO_JPEG_TIMESTAMP_NS: int = 14  # (timestamp_ns (timestamp after compressing to jpeg)
    START_IMAGE_ANNOTATION_TIMESTAMP_NS: int = 15  # (timestamp before annotating image)
    END_IMAGE_ANNOTATION_TIMESTAMP_NS: int = 16  # (timestamp after annotating image)


DEFAULT_IMAGE_DTYPE = np.uint8
FRAME_METADATA_DTYPE = np.uint64
FRAME_METADATA_SHAPE = (len(FRAME_METADATA_MODEL),)
FRAME_METADATA_SIZE_BYTES = np.dtype(FRAME_METADATA_DTYPE).itemsize * np.prod(FRAME_METADATA_SHAPE)


def create_empty_frame_metadata(
        frame_number: int,
        config: CameraConfig
) -> np.ndarray:
    metadata_array = np.zeros(FRAME_METADATA_SHAPE,
                              dtype=FRAME_METADATA_DTYPE)
    metadata_array[FRAME_METADATA_MODEL.FRAME_METADATA_INITIALIZED.value] = time.perf_counter_ns()

    metadata_array[FRAME_METADATA_MODEL.CAMERA_INDEX.value] = config.camera_index
    metadata_array[FRAME_METADATA_MODEL.IMAGE_HEIGHT.value] = config.image_shape[0]
    metadata_array[FRAME_METADATA_MODEL.IMAGE_WIDTH.value] = config.image_shape[1]
    metadata_array[FRAME_METADATA_MODEL.IMAGE_COLOR_CHANNELS.value] = config.image_shape[2]
    metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value] = frame_number

    if metadata_array.dtype != FRAME_METADATA_DTYPE:
        raise ValueError(f"Metadata array has the wrong dtype: {metadata_array.dtype}")
    return metadata_array


if __name__ == "__main__":
    print(FRAME_METADATA_MODEL)
    print(FRAME_METADATA_DTYPE)
    print(FRAME_METADATA_SHAPE)
    print(FRAME_METADATA_SIZE_BYTES)
    empty_metadata = create_empty_frame_metadata(frame_number=0, config=CameraConfig())
    print(f"empty_metadata: {empty_metadata}")
    print(f"empty_metadata dtype: {empty_metadata.dtype}")

    [print(f"{key}: {empty_metadata[key.value]}") for key in FRAME_METADATA_MODEL]
    empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()
    print(f"empty_metadata w/ timestamp: {empty_metadata}")
    [print(f"{key}: {empty_metadata[key.value]}") for key in FRAME_METADATA_MODEL]
    time_elapsed_ns = empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] - empty_metadata[
        FRAME_METADATA_MODEL.FRAME_METADATA_INITIALIZED.value]
    print(f"Time elapsed: {time_elapsed_ns} ns ({time_elapsed_ns / 1_000_000} ms, {time_elapsed_ns / 1_000_000_000} s)")
