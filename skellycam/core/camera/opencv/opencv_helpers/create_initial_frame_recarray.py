import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.types.frame_dtype_factories import create_frame_dtype


def create_initial_frame_rec_array(config: CameraConfig, ipc: CameraGroupIPC) -> np.recarray:
    # Create initial frame record array
    frame_dtype = create_frame_dtype(config)
    frame_rec_array = np.recarray(1, dtype=frame_dtype)
    # Initialize the per-frame camera identification
    frame_rec_array.frame_metadata.camera_info[0] = config.to_frame_camera_info()
    frame_rec_array.frame_metadata.frame_number[0] = -1
    frame_rec_array.frame_metadata.timebase_mapping[0] = ipc.timebase_mapping.to_numpy_record_array()
    # Initialize the image with zeros
    image_shape = (config.resolution.height, config.resolution.width, config.color_channels)
    frame_rec_array.image[0] = np.zeros(image_shape, dtype=np.uint8) + config.camera_index
    return frame_rec_array
