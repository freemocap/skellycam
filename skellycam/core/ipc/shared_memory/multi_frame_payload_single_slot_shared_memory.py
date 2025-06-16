import logging
import time

from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement

logger = logging.getLogger(__name__)


class MultiframePayloadSingleSlotSharedMemory(SharedMemoryElement):
    def put_multiframe(self,
                       mf_payload: MultiFramePayload) -> None:
        if not mf_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")

        for frame in mf_payload.frames.values():
            frame.frame_metadata.copy_to_multiframe_shm = time.perf_counter_ns()

        self.put_data(data = mf_payload.to_numpy_record_array())

    def retrieve_multiframe(self) -> MultiFramePayload:

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        mf_payload = self.re
        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        for frame in mf_payload.frames.values():
            frame.frame_metadata.copy_from_multiframe_shm = time.perf_counter_ns()
        return mf_payload

