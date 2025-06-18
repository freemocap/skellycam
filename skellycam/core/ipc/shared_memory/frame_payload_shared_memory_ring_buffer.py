import logging
import time

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_payload import FramePayload, initialize_frame_rec_array
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping

logger = logging.getLogger(__name__)


class FramePayloadSharedMemoryRingBuffer(SharedMemoryRingBuffer):

    @classmethod
    def from_config(cls, camera_config:CameraConfig, read_only: bool = False):
        return cls.create(
            example_data=initialize_frame_rec_array(camera_config= camera_config,
                                                    timebase_mapping=TimebaseMapping()), #NOTE - Dummy used for shape and dtype
            read_only=read_only,
        )
    @property
    def new_frame_available(self):
        return self.new_data_available

    def put_frame(self, frame_rec_array: np.recarray, overwrite: bool):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        frame_rec_array.frame_metadata.timestamps.copy_to_camera_shm_ns = time.perf_counter_ns()
        self.put_data(frame_rec_array, overwrite=overwrite)

    def retrieve_latest_frame(self) -> FramePayload:
        frame_rec_array = self.get_latest_data()
        frame_rec_array.frame_metadata.timestamps.retrieve_from_camera_shm_ns = time.perf_counter_ns()
        return FramePayload.from_numpy_record_array(frame_rec_array)

    def retrieve_next_frame(self) -> FramePayload:
        frame_rec_array = self.get_next_data()
        frame_rec_array.frame_metadata.timestamps.retrieve_from_camera_shm_ns = time.perf_counter_ns()
        return FramePayload.from_numpy_record_array(frame_rec_array)