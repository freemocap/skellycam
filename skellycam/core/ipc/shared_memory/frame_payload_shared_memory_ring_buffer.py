import logging
import time

import numpy as np

from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer, \
    SharedMemoryRingBufferDTO

logger = logging.getLogger(__name__)


class FramePayloadSharedMemoryRingBuffer(SharedMemoryRingBuffer):

    @property
    def new_frame_available(self):
        return self.new_data_available

    def put_frame(self, frame_rec_array:np.recarray, overwrite: bool = False):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        frame_rec_array.frame_metadata.timestamps.copy_frame_to_camera_shm = time.perf_counter_ns()
        self.put_data(frame_rec_array, overwrite=overwrite)

    def retrieve_latest_frame(self) -> FramePayload:
        frame_rec_array = self.get_latest_data()
        frame_rec_array.frame_metadata.timestamps.copy_frame_from_camera_shm = time.perf_counter_ns()
        return FramePayload.from_numpy_record_array(frame_rec_array)

    def retrieve_next_frame(self) -> FramePayload:
        frame_rec_array = self.get_next_data()
        frame_rec_array.frame_metadata.timestamps.copy_frame_from_camera_shm = time.perf_counter_ns()
        return FramePayload.from_numpy_record_array(frame_rec_array)

