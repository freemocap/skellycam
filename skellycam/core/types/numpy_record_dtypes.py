import numpy as np

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

FRAME_LIFECYCLE_TIMESTAMPS_DTYPE = np.dtype([
    ('frame_metadata_initialized', np.uint64),
    ('pre_grab_timestamp_ns', np.uint64),
    ('post_grab_timestamp_ns', np.uint64),
    ('pre_retrieve_timestamp_ns', np.uint64),
    ('post_retrieve_timestamp_ns', np.uint64),
    ('copy_to_camera_shm_buffer_timestamp_ns', np.uint64),
    ('copy_from_camera_shm_buffer_timestamp_ns', np.uint64),
    ('copy_to_multi_frame_escape_shm_buffer_timestamp_ns', np.uint64),
    ('copy_from_multi_frame_escape_shm_buffer_timestamp_ns', np.uint64),
    ('start_compress_to_jpeg_timestamp_ns', np.uint64),
    ('end_compress_to_jpeg_timestamp_ns', np.uint64),
    ('start_image_annotation_timestamp_ns', np.uint64),
    ('end_image_annotation_timestamp_ns', np.uint64),
], align=True)

FRAME_METADATA_DTYPE = np.dtype([
    ('camera_config', CAMERA_CONFIG_DTYPE),
    ('frame_number', np.uint64),
    ('timestamps', FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)],
    align=True)

TIMEBASE_MAPPING_DTYPE = np.dtype([
    ('utc_time_ns', np.uint64),
    ('perf_counter_ns', np.uint64),
    ('local_time_utc_offset', np.int32),
    ], align=True)

FRAME_DTYPE = np.dtype #actual dtype created dynamically based on camera config
MULTIFRAME_DTYPE = np.dtype #actual dtype created dynamically based on camera configs


