import logging
import time
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import DEFAULT_IMAGE_DTYPE, \
    create_empty_frame_metadata, FRAME_METADATA_DTYPE, FRAME_METADATA_MODEL
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload, MultiFrameNumpyBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import ONE_GIGABYTE, \
    SharedMemoryRingBuffer, SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber, SharedMemoryNumberDTO
from skellycam.core.types.type_overloads import CameraGroupIdString

logger = logging.getLogger(__name__)



class MultiFrameSharedMemoryRingBuffer(SharedMemoryRingBuffer):

    def put_multiframe(self,
                       mf_payload: MultiFramePayload,
                       overwrite: bool) -> None:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        if not mf_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")

        if self.read_only:
            raise ValueError("Cannot write to read-only shared memory!")

        for frame in mf_payload.frames.values():
            frame.frame_metadata.copy_to_multiframe_shm = time.perf_counter_ns()

        self.put_data(data=mf_payload.to_numpy_record_array(), overwrite=overwrite)

    def get_latest_multiframe(self) -> MultiFramePayload:

        mf_payload = MultiFramePayload.from_numpy_record_array(self.get_latest_data())
        for frame in mf_payload.frames.values():
            frame.frame_metadata.copy_from_multiframe_shm = time.perf_counter_ns()

        return mf_payload

    def get_next_multiframe(self) -> MultiFramePayload:

        mf_payload = MultiFramePayload.from_numpy_record_array(self.get_next_data())
        for frame in mf_payload.frames.values():
            frame.frame_metadata.copy_from_multiframe_shm = time.perf_counter_ns()
        return mf_payload

    def get_all_new_multiframes(self) -> list[MultiFramePayload]:
        """
        Retrieves all new multi-frames from the shared memory.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        mfs: list[MultiFramePayload] = []
        while self.new_data_available:
            mf_payload = self.get_next_multiframe()
            mfs.append(mf_payload)
        return mfs

