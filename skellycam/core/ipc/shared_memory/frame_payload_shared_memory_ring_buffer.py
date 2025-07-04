import logging
import time

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer
from skellycam.core.types.numpy_record_dtypes import create_frame_dtype

logger = logging.getLogger(__name__)


class FramePayloadSharedMemoryRingBuffer(SharedMemoryRingBuffer):

    @classmethod
    def from_config(cls,
                    camera_config: CameraConfig,
                    timebase_mapping: TimebaseMapping,
                    read_only: bool = False):
        # Create a dummy frame record array for shape and dtype
        frame_dtype = create_frame_dtype(camera_config)
        dummy_frame = np.recarray(1, dtype=frame_dtype)

        # Initialize the frame metadata
        dummy_frame.frame_metadata.camera_config = camera_config.to_numpy_record_array()[0]
        dummy_frame.frame_metadata.frame_number = -99
        dummy_frame.frame_metadata.timestamps.timebase_mapping = timebase_mapping.to_numpy_record_array()[0]

        # Initialize the image with zeros
        image_shape = (camera_config.resolution.height, camera_config.resolution.width, camera_config.color_channels)
        dummy_frame.image[0] = np.zeros(image_shape, dtype=np.uint8)

        return cls.create(
            example_data=dummy_frame,
            read_only=read_only,
        )

    @property
    def new_frame_available(self):
        return self.new_data_available

    def put_frame(self, frame_rec_array: np.recarray, overwrite: bool):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = time.perf_counter_ns()
        self.put_data(frame_rec_array, overwrite=overwrite)

    def retrieve_latest_frame(self, frame_rec_array:np.recarray) -> np.recarray:
        pre_retrieve_tik = time.perf_counter_ns()
        frame_rec_array = self.get_latest_data(frame_rec_array)
        frame_rec_array.frame_metadata.timestamps.post_retrieve_from_camera_shm_ns[0] = time.perf_counter_ns()
        frame_rec_array.frame_metadata.timestamps.pre_retrieve_from_camera_shm_ns[0] = pre_retrieve_tik
        return frame_rec_array

    def retrieve_next_frame(self, frame_rec_array:np.recarray) -> np.recarray:
        pre_retrieve_tik = time.perf_counter_ns()
        frame_rec_array = self.get_next_data(frame_rec_array)
        frame_rec_array.frame_metadata.timestamps.post_retrieve_from_camera_shm_ns[0] = time.perf_counter_ns()
        frame_rec_array.frame_metadata.timestamps.pre_retrieve_from_camera_shm_ns[0] = pre_retrieve_tik
        return frame_rec_array