import time
from enum import Enum

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig, CAMERA_CONFIG_DTYPE

FRAME_LIFECYCLE_TIMESTAMPS_DTYPE = np.dtype([
    ('frame_metadata_initialized', np.uint64), # (timestamp when the metadata was initialized)
    ('pre_grab_timestamp_ns', np.uint64),  # (timestamp before calling cv2.VideoCapture.grab())
    ('post_grab_timestamp_ns', np.uint64),  # (timestamp after calling cv2.VideoCapture.grab())
    ('pre_retrieve_timestamp_ns', np.uint64),  # (timestamp before calling cv2.VideoCapture.retrieve())
    ('post_retrieve_timestamp_ns', np.uint64),  # (timestamp after calling cv2.VideoCapture.retrieve())
    ('copy_to_camera_shm_buffer_timestamp_ns', np.uint64),  # (timestamp when frame was copied to shared memory)
    ('copy_from_camera_shm_buffer_timestamp_ns', np.uint64),  # (timestamp when frame was copied from shared memory)
    ('copy_to_multi_frame_escape_shm_buffer_timestamp_ns', np.uint64),
    # (timestamp when frame was copied to multi-frame escape shared memory)
    ('copy_from_multi_frame_escape_shm_buffer_timestamp_ns', np.uint64),
    # (timestamp when frame was copied from multi-frame escape shared memory)
    ('start_compress_to_jpeg_timestamp_ns', np.uint64),  # (timestamp before compressing to jpeg)
    ('end_compress_to_jpeg_timestamp_ns', np.uint64),  # (timestamp_ns (timestamp after compressing to jpeg)
    ('start_image_annotation_timestamp_ns', np.uint64),  # (timestamp before annotating image)
    ('end_image_annotation_timestamp_ns', np.uint64),  # (timestamp after annotating image)

])
FRAME_METADATA_DTYPE = np.dtype([
    ('camera_config', CAMERA_CONFIG_DTYPE),
    ('frame_number', np.uint64), # (The number of frames that have been captured by the camera since it was started)
    ('timestamps', FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)
])


# Calculate the size in bytes
FRAME_METADATA_SIZE_BYTES = FRAME_METADATA_DTYPE.itemsize


def create_empty_frame_metadata(
        frame_number: int,
        config: CameraConfig
) -> np.recarray:
    # Create an empty record array with one row
    metadata_array = np.recarray((1,), dtype=FRAME_METADATA_DTYPE)[0]

    # Initialize with current timestamp
    metadata_array.timestamps.frame_metadata_initialized = time.perf_counter_ns()

    # Set camera configuration values
    metadata_array.camera_config = config.to_numpy_record_array()
    metadata_array.frame_number = frame_number

    return metadata_array


if __name__ == "__main__":
    print(f"FRAME_METADATA_DTYPE: {FRAME_METADATA_DTYPE}")
    print(f"FRAME_METADATA_SIZE_BYTES: {FRAME_METADATA_SIZE_BYTES}")

    empty_metadata = create_empty_frame_metadata(frame_number=0, config=CameraConfig())
    print(f"empty_metadata: {empty_metadata}")
    print(f"empty_metadata dtype: {empty_metadata.dtype}")

    # Print all fields
    for field_name in empty_metadata.dtype.names:
        print(f"{field_name}: {empty_metadata[field_name]}")

    # Set a timestamp
    empty_metadata.timestamps.pre_retrieve_timestamp_ns = time.perf_counter_ns()
    print(f"empty_metadata w/ timestamp: {empty_metadata}")

    # Calculate time elapsed
    time_elapsed_ns = empty_metadata.timestamps.pre_retrieve_timestamp_ns - empty_metadata.timestamps.frame_metadata_initialized
    print(f"Time elapsed: {time_elapsed_ns} ns ({time_elapsed_ns / 1_000_000} ms, {time_elapsed_ns / 1_000_000_000} s)")