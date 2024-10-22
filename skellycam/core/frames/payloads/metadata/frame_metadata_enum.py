import time
from enum import Enum

import numpy as np

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig


class FRAME_METADATA_MODEL(Enum):
    """
    An enum to represent the metadata associated with a frame of image data.
    The value of each enum member corresponds to the index of that value in the metadata np.ndarray.
    We will store the metadata in an numpy array while we're doing the shared memory nonsense, and convert to a Pydantic model when we're safely away from Camera land.
    """
    CAMERA_ID: int = 0  # CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)
    FRAME_NUMBER: int = 1  # (The number of frames that have been captured by the camera since it was started)
    RESOLUTION_WIDTH: int = 2  # (The width of the image in pixels)
    RESOLUTION_HEIGHT: int = 3  # (The height of the image in pixels)
    COLOR_CHANNELS: int = 4  # (The number of color channels in the image)
    IMAGE_ROTATION: int = 5  # (The rotation (cv2) value of the image (3:N/A, 0:cv2.ROTATE_90_CLOCKWISE, 1:cv2.ROTATE_180, 2:cv2.ROTATE_90_COUNTERCLOCKWISE))
    IMAGE_EXPOSURE_SETTING_NEG: int = 6  # (The exposure setting of the camera when the image was captured)
    FRAME_METADATA_INITIALIZED: int = 7  # (timestamp when the metadata was initialized)
    PRE_GRAB_TIMESTAMP_NS: int = 8  # (timestamp before calling cv2.VideoCapture.grab())
    POST_GRAB_TIMESTAMP_NS: int = 9  # (timestamp after calling cv2.VideoCapture.grab())
    PRE_RETRIEVE_TIMESTAMP_NS: int = 10  # (timestamp before calling cv2.VideoCapture.retrieve())
    POST_RETRIEVE_TIMESTAMP_NS: int = 11  # (timestamp after calling cv2.VideoCapture.retrieve())
    COPY_TO_BUFFER_TIMESTAMP_NS: int = 12  # (timestamp when frame was copied to shared memory)
    COPY_FROM_BUFFER_TIMESTAMP_NS: int = 13  # (timestamp when frame was copied from shared memory)
    START_COMPRESS_TO_JPEG_TIMESTAMP_NS: int = 14  # (timestamp before compressing to jpeg)
    END_COMPRESS_TO_JPEG_TIMESTAMP_NS: int = 15  # (timestamp_ns (timestamp after compressing to jpeg)
    START_IMAGE_ANNOTATION_TIMESTAMP_NS: int = 16  # (timestamp before annotating image)
    END_IMAGE_ANNOTATION_TIMESTAMP_NS: int = 17  # (timestamp after annotating image)


DEFAULT_IMAGE_DTYPE = np.uint8
FRAME_METADATA_DTYPE = np.uint64
FRAME_METADATA_SHAPE = (len(FRAME_METADATA_MODEL),)
FRAME_METADATA_SIZE_BYTES = np.dtype(FRAME_METADATA_DTYPE).itemsize * np.prod(FRAME_METADATA_SHAPE)


def create_empty_frame_metadata(
        camera_id: int,
        camera_config: CameraConfig,
        frame_number: int
) -> np.ndarray:
    metadata_array = np.zeros(FRAME_METADATA_SHAPE,
                              dtype=FRAME_METADATA_DTYPE)
    metadata_array[FRAME_METADATA_MODEL.FRAME_METADATA_INITIALIZED.value] = time.perf_counter_ns()

    metadata_array[FRAME_METADATA_MODEL.CAMERA_ID.value] = camera_id
    metadata_array[FRAME_METADATA_MODEL.FRAME_NUMBER.value] = frame_number
    metadata_array[FRAME_METADATA_MODEL.RESOLUTION_WIDTH.value] = camera_config.resolution.width
    metadata_array[FRAME_METADATA_MODEL.RESOLUTION_HEIGHT.value] = camera_config.resolution.height
    metadata_array[FRAME_METADATA_MODEL.COLOR_CHANNELS.value] = camera_config.color_channels
    metadata_array[FRAME_METADATA_MODEL.IMAGE_ROTATION.value] = camera_config.rotation.to_opencv_constant()
    metadata_array[FRAME_METADATA_MODEL.IMAGE_EXPOSURE_SETTING_NEG.value] = -camera_config.exposure

    if metadata_array.dtype != FRAME_METADATA_DTYPE:
        raise ValueError(f"Metadata array has the wrong dtype: {metadata_array.dtype}")
    return metadata_array


if __name__ == "__main__":
    print(FRAME_METADATA_MODEL)
    print(FRAME_METADATA_DTYPE)
    print(FRAME_METADATA_SHAPE)
    print(FRAME_METADATA_SIZE_BYTES)
    empty_metadata = create_empty_frame_metadata(camera_config=CameraConfig(camera_id=0), camera_id=0, frame_number=0)
    print(f"empty_metadata: {empty_metadata}")
    print(f"empty_metadata dtype: {empty_metadata.dtype}")

    [print(f"{key}: {empty_metadata[key.value]}") for key in FRAME_METADATA_MODEL]
    empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] = time.perf_counter_ns()
    print(f"empty_metadata w/ timestamp: {empty_metadata}")
    [print(f"{key}: {empty_metadata[key.value]}") for key in FRAME_METADATA_MODEL]
    time_elapsed_ns = empty_metadata[FRAME_METADATA_MODEL.PRE_RETRIEVE_TIMESTAMP_NS.value] - empty_metadata[
        FRAME_METADATA_MODEL.FRAME_METADATA_INITIALIZED.value]
    print(f"Time elapsed: {time_elapsed_ns} ns ({time_elapsed_ns / 1_000_000} ms, {time_elapsed_ns / 1_000_000_000} s)")
