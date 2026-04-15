import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.types.numpy_record_dtypes import (
    FRAME_METADATA_DTYPE,
    FRAME_DTYPE,
    MULTIFRAME_DTYPE,
)


def create_frame_dtype(config: CameraConfig) -> FRAME_DTYPE:
    """
    Create a numpy dtype for the frame data based on the camera configuration.
    Contains per-frame metadata and the raw image pixels.
    """
    return np.dtype(
        [
            ("frame_metadata", FRAME_METADATA_DTYPE),
            (
                "image",
                np.uint8,
                (config.resolution.height, config.resolution.width, config.color_channels),
            ),
        ],
        align=True,
    )


def create_multiframe_dtype(camera_configs: dict[str, CameraConfig]) -> MULTIFRAME_DTYPE:
    """
    Create a numpy dtype for multiple frames based on a dictionary of camera configurations.
    Each camera gets its own field in the dtype, keyed by camera ID.
    """
    fields = [
        (camera_id, create_frame_dtype(config))
        for camera_id, config in camera_configs.items()
    ]
    return np.dtype(fields, align=True)
