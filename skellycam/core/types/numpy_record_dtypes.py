import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np

from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import ONE_MEGABYTE
from skellycam.core.types.type_overloads import FrameNumberInt

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from skellycam.core.camera.config.camera_config import CameraConfig

CAMERA_CONFIG_DTYPE = np.dtype([
    ('camera_id', 'U1000'),
    ('camera_index', np.int32),
    ('camera_name', 'U1000'),
    ('use_this_camera', np.bool_),
    ('resolution_height', np.int32),
    ('resolution_width', np.int32),
    ('color_channels', np.int32),
    ('pixel_format', 'U8'),
    ('exposure_mode', 'U32'),
    ('exposure', np.int32),
    ('framerate', np.float32),
    ('rotation', 'U8'),
    ('capture_fourcc', 'U4'),
    ('writer_fourcc', 'U4'),
], align=True)
TIMEBASE_MAPPING_DTYPE = np.dtype([
    ('utc_time_ns', np.uint64),
    ('perf_counter_ns', np.uint64),
    ('local_time_utc_offset', np.int32),
], align=True)

FRAME_LIFECYCLE_TIMESTAMPS_DTYPE = np.dtype([
    ('timebase_mapping', TIMEBASE_MAPPING_DTYPE),
    ('frame_initialized_ns', np.uint64),
    ('pre_frame_grab_ns', np.uint64),
    ('post_frame_grab_ns', np.uint64),
    ('pre_frame_retrieve_ns', np.uint64),
    ('post_frame_retrieve_ns', np.uint64),
    ('pre_copy_to_camera_shm_ns', np.uint64),
    ('pre_retrieve_from_camera_shm_ns', np.uint64),
    ('post_retrieve_from_camera_shm_ns', np.uint64),
    ('pre_copy_to_multiframe_shm_ns', np.uint64),
    ('pre_retrieve_from_multiframe_shm_ns', np.uint64),
    ('post_retrieve_from_multiframe_shm_ns', np.uint64),
], align=True)

FRAME_METADATA_DTYPE = np.dtype([
    ('camera_config', CAMERA_CONFIG_DTYPE),
    ('frame_number', np.int64),
    ('timestamps', FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)
],
    align=True)

FRAME_DTYPE = np.dtype  # actual dtype created dynamically based on camera config
MULTIFRAME_DTYPE = np.dtype  # actual dtype created dynamically based on camera configs


def create_frame_dtype(config: 'CameraConfig') -> FRAME_DTYPE:
    """
    Create a numpy dtype for the frame metadata based on the camera configuration.
    """
    return np.dtype([
        ('frame_metadata', FRAME_METADATA_DTYPE),
        ('image', np.uint8, (config.resolution.height, config.resolution.width, config.color_channels)),
    ], align=True)


def create_multiframe_dtype(camera_configs: dict[str, 'CameraConfig']) -> MULTIFRAME_DTYPE:
    """
    Create a numpy dtype for multiple frames based on a dictionary of camera configurations.
    Each camera gets its own field in the dtype.

    Args:
        camera_configs: Dictionary mapping camera IDs to their configurations

    Returns:
        A numpy dtype that can store frames from multiple cameras
    """
    fields = []
    for camera_id, config in camera_configs.items():
        # Create a field for each camera using its ID as the field name
        # Each field contains a frame with the camera-specific dtype
        fields.append((camera_id, create_frame_dtype(config)))
    return np.dtype(fields, align=True)


FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE = np.dtype([
    ('message_type', '<u1'),  # 1 byte: 0 = payload_header, 1 = frame_metadata, 2 = payload_footer
    ('frame_number', '<i8'),  # 8 bytes, little-endian int64
    ('number_of_cameras', '<i4'),  # 4 bytes, little-endian int32
], align=True)

FRONTEND_FRAME_HEADER_DTYPE = np.dtype([
    ('message_type', '<u1'),  # 1 byte: 0 = payload_header, 1 = frame_metadata, 2 = payload_footer
    ('frame_number', '<i8'),  # 8 bytes, little-endian int64
    ('camera_id', 'S16'),  # 16 bytes fixed-length camera ID
    ('image_width', '<i4'),  # 4 bytes, little-endian int32
    ('image_height', '<i4'),  # 4 bytes, little-endian int32
    ('color_channels', '<i4'),  # 4 bytes, little-endian int32
    ('jpeg_string_length', '<i4'),  # 4 bytes, length of the JPEG string, little-endian int32
], align=True)

JPEG_ENCODING_PARAMETERS = [int(cv2.IMWRITE_JPEG_QUALITY), 80]


def create_frontend_payload_from_mf_recarray(mf_rec_array: np.recarray, resize_image: float = 0.5,
                                             jpeg_encoding_parameters: list[int] = JPEG_ENCODING_PARAMETERS) -> tuple[
    FrameNumberInt, bytes]:
    """
    Convert a multi-frame record array into a list of record arrays for each camera.
     first element is the header, which tell the frontend how many cameras are in the payload.
     then for each camera, we send a frame metadata record array (including the length of the JPEG string), followed by the JPEG image data.
     We end with a footer record array that indicates the end of the payload, allowing verification that all data was received correctly.

    We then convert that list into a bytes object for websocket transmission.
    """
    camera_ids = mf_rec_array.dtype.names
    frame_numbers = [mf_rec_array[camera_id].frame_metadata.frame_number[0] for camera_id in camera_ids]
    if len(set(frame_numbers)) != 1:
        raise ValueError("All cameras in the multi-frame record array must have the same frame number.")
    frame_number = frame_numbers[0]
    number_of_cameras = len(camera_ids)

    # Pre-allocate approximate size to avoid reallocations
    estimated_size = 13 + (number_of_cameras * (41 + ONE_MEGABYTE)) + 13  # Header + frames + footer
    bytes_payload = bytearray(estimated_size)
    current_pos = 0

    # Add header
    payload_header = np.array([(0, frame_number, number_of_cameras)],
                              dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    header_bytes = payload_header.tobytes()


    bytes_payload[current_pos:current_pos + len(header_bytes)] = header_bytes
    current_pos += len(header_bytes)

    for camera_id in camera_ids:
        frame_recarray = mf_rec_array[camera_id][0]
        image = frame_recarray.image[:]
        # Faster resize using nearest neighbor interpolation
        resized_img = cv2.resize(image, dsize=None, fx=resize_image, fy=resize_image,
                                 interpolation=cv2.INTER_NEAREST)
        _, jpeg_data = cv2.imencode('.jpg', resized_img, jpeg_encoding_parameters)
        jpeg_string = jpeg_data.tobytes()
        jpeg_string_length = len(jpeg_string)
        frame_header = np.array([(1,
                                  frame_number,
                                  camera_id.encode('utf-8'),
                                  frame_recarray.image.shape[0],
                                  frame_recarray.image.shape[1],
                                  frame_recarray.image.shape[2],
                                  jpeg_string_length)], dtype=FRONTEND_FRAME_HEADER_DTYPE)
        frame_header_bytes = frame_header.tobytes()
        # Ensure enough space in bytearray
        if current_pos + len(frame_header_bytes) + jpeg_string_length > len(bytes_payload):
            og_len = len(bytes_payload)
            bytes_payload.extend(bytearray(max(1000000, len(frame_header_bytes) + jpeg_string_length)))
            logging.warning(
                f"Payload size ({og_len}bytes) exceeded pre-allocated size, resized to {len(bytes_payload)} bytes - change default pre-allocated size!")

        # Copy data
        bytes_payload[current_pos:current_pos + len(frame_header_bytes)] = frame_header_bytes
        current_pos += len(frame_header_bytes)
        bytes_payload[current_pos:current_pos + jpeg_string_length] = jpeg_string
        current_pos += jpeg_string_length

    # Add footer
    payload_footer = np.array([(2, frame_number, number_of_cameras)],
                              dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    footer_bytes = payload_footer.tobytes()

    # Ensure enough space
    if current_pos + len(footer_bytes) > len(bytes_payload):
        og_len = len(bytes_payload)
        bytes_payload.extend(bytearray(len(footer_bytes)))
        logging.warning(
            f"Payload size ({og_len}bytes) exceeded pre-allocated size, resized to {len(bytes_payload)} bytes - change default pre-allocated size!")

    bytes_payload[current_pos:current_pos + len(footer_bytes)] = footer_bytes
    current_pos += len(footer_bytes)

    frontend_bytes = bytes_payload[:current_pos]
    return frame_number, frontend_bytes
