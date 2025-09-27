import logging

import cv2
import numpy as np
from numpy import typing as npt

logger = logging.getLogger(__name__)

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
    ('rotation', np.int32),
    ('capture_fourcc', 'U4'),
    ('writer_fourcc', 'U4'),
], align=True)

TIMEBASE_MAPPING_DTYPE = np.dtype([
    ('utc_time_ns', np.int64),
    ('perf_counter_ns', np.int64),
    ('local_time_utc_offset', np.int32),
], align=True)

FRAME_LIFECYCLE_TIMESTAMPS_DTYPE = np.dtype([
    ('initialized_ns', np.int64),
    ('pre_frame_grab_ns', np.int64),
    ('post_frame_grab_ns', np.int64),
    ('pre_frame_retrieve_ns', np.int64),
    ('post_frame_retrieve_ns', np.int64),
    ('pre_copy_to_camera_shm_ns', np.int64),
    ('post_copy_to_camera_shm_ns', np.int64),
    ('pre_frame_record_ns', np.int64),
    ('post_frame_record_ns', np.int64),
], align=True)

# Define the dtype for calculated durations
FRAME_DURATION_DTYPE = np.dtype([
    ('idle_before_frame_grab_ns', np.int64),
    ('during_frame_grab_ns', np.int64),
    ('idle_before_retrieve_ns', np.int64),
    ('during_frame_retrieve_ns', np.int64),
    ('idle_before_copy_to_camera_shm_ns', np.int64),
    ('during_copy_to_camera_shm_ns', np.int64),
    ('idle_before_frame_record_ns', np.int64),
    ('during_frame_record_ns', np.int64),
    ('total_frame_processing_time_ns', np.int64),
    ('total_camera_idle_time_ns', np.int64),
])

CAMERA_TIMESTAMPS_CSV_ROW_DTYPE = np.dtype([
    ('recording_frame_number', np.int64),
    ('connection_frame_number', np.int64),
    ('timestamp.from_recording_start.sec', np.float64),
    ('timestamp.utc.seconds', np.float64),
    ('timestamp.local.iso8601', 'U32'),
    ('timestamp.perf_counter_ns.ns', np.int64),
    ("from_previous.frame_duration.ms", np.float64),
    ("from_previous.framerate.hz", np.float64),
    # Include all timestamp fields with csv-friendly names
    ('frame.initialized.ns', np.int64),
    ('frame.pre_frame_grab.ns', np.int64),
    ('frame.post_frame_grab.ns', np.int64),
    ('frame.pre_frame_retrieve.ns', np.int64),
    ('frame.post_frame_retrieve.ns', np.int64),
    ('frame.pre_copy_to_camera_shm.ns', np.int64),
    ('frame.post_copy_to_camera_shm.ns', np.int64),
    ('frame.pre_frame_record.ns', np.int64),
    ('frame.post_frame_record.ns', np.int64),
    # Include all duration fields with csv-friendly names
    ('duration.idle_before_frame_grab.ns', np.int64),
    ('duration.during_frame_grab.ns', np.int64),
    ('duration.idle_before_retrieve.ns', np.int64),
    ('duration.during_frame_retrieve.ns', np.int64),
    ('duration.idle_before_copy_to_camera_shm.ns', np.int64),
    ('duration.during_copy_to_camera_shm.ns', np.int64),
    ('duration.idle_before_frame_record.ns', np.int64),
    ('duration.during_frame_record.ns', np.int64),
    ('total.frame_processing_time.ns', np.int64),
    ('total.camera_idle_time.ns', np.int64),
])

MULTI_FRAME_TIMESTAMP_CSV_ROW = np.dtype([
    ('multiframe_number', np.int64),
    ('timestamp.from_recording_start.sec', np.float64),
    ('timestamp.perf_counter_ns.ns', np.float64),
    ('timestamp.utc.seconds', np.float64),
    ('timestamp.local.iso8601', 'U32'),
    ('from_previous.frame_duration.ms', np.float64),
    ('from_previous.framerate.hz', np.float64),
    ('inter_camera.frame_grab_range.ms', np.float64),

    # Lifespan timestamp fields with statistical measures
    ('frame.initialized.ms.mean', np.float64),
    ('frame.initialized.ms.median', np.float64),
    ('frame.initialized.ms.standard_deviation', np.float64),
    ('frame.initialized.ms.range', np.float64),
    ('frame.initialized.proportion.coefficient_of_variation', np.float64),

    ('frame.pre_frame_grab.ms.mean', np.float64),
    ('frame.pre_frame_grab.ms.median', np.float64),
    ('frame.pre_frame_grab.ms.standard_deviation', np.float64),
    ('frame.pre_frame_grab.ms.range', np.float64),
    ('frame.pre_frame_grab.proportion.coefficient_of_variation', np.float64),

    ('frame.post_frame_grab.ms.mean', np.float64),
    ('frame.post_frame_grab.ms.median', np.float64),
    ('frame.post_frame_grab.ms.standard_deviation', np.float64),
    ('frame.post_frame_grab.ms.range', np.float64),
    ('frame.post_frame_grab.proportion.coefficient_of_variation', np.float64),

    ('frame.pre_frame_retrieve.ms.mean', np.float64),
    ('frame.pre_frame_retrieve.ms.median', np.float64),
    ('frame.pre_frame_retrieve.ms.standard_deviation', np.float64),
    ('frame.pre_frame_retrieve.ms.range', np.float64),
    ('frame.pre_frame_retrieve.proportion.coefficient_of_variation', np.float64),

    ('frame.post_frame_retrieve.ms.mean', np.float64),
    ('frame.post_frame_retrieve.ms.median', np.float64),
    ('frame.post_frame_retrieve.ms.standard_deviation', np.float64),
    ('frame.post_frame_retrieve.ms.range', np.float64),
    ('frame.post_frame_retrieve.proportion.coefficient_of_variation', np.float64),

    ('frame.pre_copy_to_camera_shm.ms.mean', np.float64),
    ('frame.pre_copy_to_camera_shm.ms.median', np.float64),
    ('frame.pre_copy_to_camera_shm.ms.standard_deviation', np.float64),
    ('frame.pre_copy_to_camera_shm.ms.range', np.float64),
    ('frame.pre_copy_to_camera_shm.proportion.coefficient_of_variation', np.float64),

    ('frame.post_copy_to_camera_shm.ms.mean', np.float64),
    ('frame.post_copy_to_camera_shm.ms.median', np.float64),
    ('frame.post_copy_to_camera_shm.ms.standard_deviation', np.float64),
    ('frame.post_copy_to_camera_shm.ms.range', np.float64),
    ('frame.post_copy_to_camera_shm.proportion.coefficient_of_variation', np.float64),

    ('frame.pre_frame_record.ms.mean', np.float64),
    ('frame.pre_frame_record.ms.median', np.float64),
    ('frame.pre_frame_record.ms.standard_deviation', np.float64),
    ('frame.pre_frame_record.ms.range', np.float64),
    ('frame.pre_frame_record.proportion.coefficient_of_variation', np.float64),

    ('frame.post_frame_record.ms.mean', np.float64),
    ('frame.post_frame_record.ms.median', np.float64),
    ('frame.post_frame_record.ms.standard_deviation', np.float64),
    ('frame.post_frame_record.ms.range', np.float64),
    ('frame.post_frame_record.proportion.coefficient_of_variation', np.float64),

    # Lifespan duration fields with statistical measures
    ('duration.idle_before_frame_grab.ms.mean', np.float64),
    ('duration.idle_before_frame_grab.ms.median', np.float64),
    ('duration.idle_before_frame_grab.ms.standard_deviation', np.float64),
    ('duration.idle_before_frame_grab.ms.range', np.float64),
    ('duration.idle_before_frame_grab.proportion.coefficient_of_variation', np.float64),

    ('duration.during_frame_grab.ms.mean', np.float64),
    ('duration.during_frame_grab.ms.median', np.float64),
    ('duration.during_frame_grab.ms.standard_deviation', np.float64),
    ('duration.during_frame_grab.ms.range', np.float64),
    ('duration.during_frame_grab.proportion.coefficient_of_variation', np.float64),

    ('duration.idle_before_retrieve.ms.mean', np.float64),
    ('duration.idle_before_retrieve.ms.median', np.float64),
    ('duration.idle_before_retrieve.ms.standard_deviation', np.float64),
    ('duration.idle_before_retrieve.ms.range', np.float64),
    ('duration.idle_before_retrieve.proportion.coefficient_of_variation', np.float64),

    ('duration.during_frame_retrieve.ms.mean', np.float64),
    ('duration.during_frame_retrieve.ms.median', np.float64),
    ('duration.during_frame_retrieve.ms.standard_deviation', np.float64),
    ('duration.during_frame_retrieve.ms.range', np.float64),
    ('duration.during_frame_retrieve.proportion.coefficient_of_variation', np.float64),

    ('duration.idle_before_copy_to_camera_shm.ms.mean', np.float64),
    ('duration.idle_before_copy_to_camera_shm.ms.median', np.float64),
    ('duration.idle_before_copy_to_camera_shm.ms.standard_deviation', np.float64),
    ('duration.idle_before_copy_to_camera_shm.ms.range', np.float64),
    ('duration.idle_before_copy_to_camera_shm.proportion.coefficient_of_variation', np.float64),

    ('duration.during_copy_to_camera_shm.ms.mean', np.float64),
    ('duration.during_copy_to_camera_shm.ms.median', np.float64),
    ('duration.during_copy_to_camera_shm.ms.standard_deviation', np.float64),
    ('duration.during_copy_to_camera_shm.ms.range', np.float64),
    ('duration.during_copy_to_camera_shm.proportion.coefficient_of_variation', np.float64),

    ('duration.idle_before_frame_record.ms.mean', np.float64),
    ('duration.idle_before_frame_record.ms.median', np.float64),
    ('duration.idle_before_frame_record.ms.standard_deviation', np.float64),
    ('duration.idle_before_frame_record.ms.range', np.float64),
    ('duration.idle_before_frame_record.proportion.coefficient_of_variation', np.float64),

    ('duration.during_frame_record.ms.mean', np.float64),
    ('duration.during_frame_record.ms.median', np.float64),
    ('duration.during_frame_record.ms.standard_deviation', np.float64),
    ('duration.during_frame_record.ms.range', np.float64),
    ('duration.during_frame_record.proportion.coefficient_of_variation', np.float64),

    ('total.frame_processing_time.ms.mean', np.float64),
    ('total.frame_processing_time.ms.median', np.float64),
    ('total.frame_processing_time.ms.standard_deviation', np.float64),
    ('total.frame_processing_time.ms.range', np.float64),
    ('total.frame_processing_time.proportion.coefficient_of_variation', np.float64),

    ('total.camera_idle_time.ms.mean', np.float64),
    ('total.camera_idle_time.ms.median', np.float64),
    ('total.camera_idle_time.ms.standard_deviation', np.float64),
    ('total.camera_idle_time.ms.range', np.float64),
    ('total.camera_idle_time.proportion.coefficient_of_variation', np.float64),


])

# Define the dtype for statistics
#NOTE - adding `_value` suffix to avoid conflict with numpy's built-in statistics functions
STATS_DTYPE = np.dtype([
    ('mean_value', np.float64),
    ('median_value', np.float64),
    ('standard_deviation_value', np.float64),
    ('coefficient_of_variation_value', np.float64),
    ('min_value', np.float64),
    ('max_value', np.float64),
    ('range_value', np.float64),
])

FRAME_METADATA_DTYPE = np.dtype([
    ('camera_config', CAMERA_CONFIG_DTYPE),
    ('frame_number', np.int64),
    ('timebase_mapping', TIMEBASE_MAPPING_DTYPE),
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
    ('camera_index', '<i4'),  # 4 bytes, little-endian int32
    ('image_width', '<i4'),  # 4 bytes, little-endian int32
    ('image_height', '<i4'),  # 4 bytes, little-endian int32
    ('color_channels', '<i4'),  # 4 bytes, little-endian int32
    ('jpeg_string_length', '<i4'),  # 4 bytes, length of the JPEG string, little-endian int32
], align=True)

JPEG_ENCODING_PARAMETERS = [int(cv2.IMWRITE_JPEG_QUALITY), 80]


FrameMetadataArray = npt.NDArray[np.recarray]  # Arrays with timestamp record dtype
AllTimestampsArray = npt.NDArray[np.recarray]  # Arrays with timestamp record dtype, shape (num_cameras, num_frames)

AllDurationsArray = npt.NDArray[np.recarray]  # Arrays with durations record dtype, shape (num_cameras, num_frames)
AllFrameGrabTimestampsArray = npt.NDArray[np.int64]     # Arrays with int64 dtype, shape (num_cameras, num_frames), midpoints between pre_frame_grab_ns and post_frame_grab_ns
TimestampsArray = npt.NDArray[np.recarray]  # Arrays with timestamp record dtype, (for a single camera/frame)
DurationArray = npt.NDArray[np.recarray]   # Arrays with duration record dtype
StatsArray = npt.NDArray[np.recarray]      # Arrays with statistics record dtype
FloatArray = npt.NDArray[np.float64]       # Arrays of float64 values
IntArray = npt.NDArray[np.int64]           # Arrays of int64 values
BoolArray = npt.NDArray[np.bool_]          # Arrays of boolean values
