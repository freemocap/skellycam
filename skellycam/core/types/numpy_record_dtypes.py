from typing import TYPE_CHECKING

import cv2
import numpy as np

from skellycam.core.types.type_overloads import FrameNumberInt

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

FRONTEND_PAYLOAD_HEADER_DTYPE = np.dtype([
    ('message_type', 'u1'),           # 0 = payload_header, 1 = frame_metadata, 2 = image, 3 = payload_footer
    ('frame_number', np.int64),       # 8 bytes
    ('number_of_cameras', np.int32),  # 4 bytes
], align=True)

FRONTEND_FRAME_HEADER_DTYPE = np.dtype([
    ('message_type', 'u1'),           # 0 = payload_header, 1 = frame_metadata, 2 = image, 3 = payload_footer
    ('frame_number', np.int64),       # 8 bytes
    ('camera_id', 'S16'),             # 16 bytes fixed-length camera ID
    ('image_width', np.int32),        # 4 bytes
    ('image_height', np.int32),       # 4 bytes
    ('color_channels', np.int32),     # 4 bytes
    ('jpeg_string_length', np.int32),  # 4 bytes, length of the JPEG string
], align=True)

FRONTEND_PAYLOAD_FOOTER_DTYPE = np.dtype([
    ('message_type', 'u1'),           # 0 = payload_header, 1 = frame_metadata, 2 = image, 3 = payload_footer
    ('frame_number', np.int64),       # 8 bytes
    ('number_of_cameras', np.int32),  # 4 bytes
], align=True)

def create_frontend_payload_from_mf_recarray(mf_rec_array: np.recarray, resize_image:float=0.5, jpeg_quality:int=90) -> tuple[FrameNumberInt, bytes]:
    """
    Convert a multi-frame record array into a list of record arrays for each camera.
     first element is the header, which tell the frontend how many cameras are in the payload.
     then for each camera, we send a frame metadata record array (including the length of the JPEG string), followed by the JPEG image data.
     We end with a footer record array that indicates the end of the payload, allowing verification that all data was received correctly.

    We then convert that list into a bytes object for websocket transmission.
    """
    camera_ids = mf_rec_array.dtype.names
    frame_numbers = [mf_rec_array[camera_id].frame_number[0] for camera_id in camera_ids]
    if len(set(frame_numbers)) != 1:
        raise ValueError("All cameras in the multi-frame record array must have the same frame number.")
    frame_number = frame_numbers[0]
    number_of_cameras = len(camera_ids)

    bytes_payload = bytearray()


    payload_header = np.array([(0, frame_number, number_of_cameras)],
                              dtype=FRONTEND_PAYLOAD_HEADER_DTYPE)
    bytes_payload.extend(payload_header.tobytes())
    for camera_id in camera_ids:
        frame_recarray = mf_rec_array[camera_id][0]
        image = frame_recarray.image[0]

        jpeg_string = (cv2.imencode('.jpg',
                                   cv2.resize(image, dsize=None, fx=resize_image, fy=resize_image),
                                   [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])[1]
                       .tobytes())
        jpeg_string_length = len(jpeg_string)
        frame_header = np.array([(1,
                                  frame_number,
                                  camera_id.encode('utf-8'),
                                  frame_recarray.image.shape[0],
                                  frame_recarray.image.shape[1],
                                  frame_recarray.image.shape[2],
                                  jpeg_string_length)],dtype=FRONTEND_FRAME_HEADER_DTYPE)
        bytes_payload.extend(frame_header.tobytes())
        bytes_payload.extend(jpeg_string)

    payload_footer = np.array([(3, frame_number, number_of_cameras)],
                              dtype=FRONTEND_PAYLOAD_FOOTER_DTYPE)
    bytes_payload.extend(payload_footer.tobytes())
    return frame_number, bytes_payload






