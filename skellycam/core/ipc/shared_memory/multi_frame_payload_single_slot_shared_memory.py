import logging
import time

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElement

logger = logging.getLogger(__name__)


class MultiframePayloadSingleSlotSharedMemory(SharedMemoryElement):
    @classmethod
    def from_configs(cls, camera_configs:CameraConfigs, read_only:bool):
        return cls.create(
            dtype=MultiFramePayload.create_dummy(camera_configs=camera_configs).to_numpy_record_array().dtype,
            read_only=read_only,
        )
    def put_multiframe(self,
                       mf_payload: MultiFramePayload) -> None:
        if not mf_payload.full:
            raise ValueError("Cannot write incomplete multi-frame payload to shared memory!")

        for frame in mf_payload.frames.values():
            frame.frame_metadata.timestamps.copy_to_multi_frame_escape_shm_buffer_timestamp_ns = time.perf_counter_ns()

        self.put_data(data = mf_payload.to_numpy_record_array())

    def retrieve_multiframe(self) -> MultiFramePayload| None:

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        mf_payload: MultiFramePayload|None = None
        mf_rec_array = self.retrieve_data()
        if mf_rec_array is None:
            return None
        mf_payload = MultiFramePayload.from_numpy_record_array(mf_rec_array=mf_rec_array)
        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        for frame in mf_payload.frames.values():
            frame.frame_metadata.timestamps.copy_to_multi_frame_escape_shm_buffer_timestamp_ns = time.perf_counter_ns()
        return mf_payload

