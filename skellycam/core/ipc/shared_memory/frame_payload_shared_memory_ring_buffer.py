import logging
import time

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer

logger = logging.getLogger(__name__)


class FramePayloadSharedMemoryRingBuffer(SharedMemoryRingBuffer):

    @classmethod
    def from_config(cls, camera_config:CameraConfig, read_only: bool = False):
        return cls.create(
            example_data=FramePayload.create_dummy(camera_config=camera_config).to_numpy_record_array(), #NOTE - Dummy used for shape and dtype
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

    def retrieve_latest_frame(self, frame:FramePayload|None=None) -> FramePayload:
        frame_rec_array = self.get_latest_data()
        frame_rec_array.frame_metadata.timestamps.retrieve_from_camera_shm_ns = time.perf_counter_ns()
        if frame is None:
            frame = FramePayload.create_from_numpy_record_array(frame_rec_array)
        else:
            frame.update_from_numpy_record_array(frame_rec_array)
        return frame

    def retrieve_next_frame(self, frame:FramePayload|None=None) -> FramePayload:
        frame_rec_array = self.get_next_data()
        frame_rec_array.frame_metadata.timestamps.retrieve_from_camera_shm_ns = time.perf_counter_ns()
        if frame is None:
            frame =  FramePayload.create_from_numpy_record_array(frame_rec_array)
        else:
            frame.update_from_numpy_record_array(frame_rec_array)
        return frame