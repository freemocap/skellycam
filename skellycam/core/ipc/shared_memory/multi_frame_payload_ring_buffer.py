import logging
import time

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload, initialize_multi_frame_rec_array
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)



class MultiFrameSharedMemoryRingBuffer(SharedMemoryRingBuffer):
    @classmethod
    def from_configs(cls,
                    camera_configs: CameraConfigs,
                    read_only: bool = False) -> "MultiFrameSharedMemoryRingBuffer":
        return cls.create(
            example_data=initialize_multi_frame_rec_array(camera_configs=camera_configs,
                                                          frame_number=0), #NOTE - Dummy used for shape and dtype
            read_only=read_only,
        )

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
            frame.frame_metadata.timestamps.copy_to_multiframe_shm_ns = time.perf_counter_ns()

        self.put_data(data=mf_payload.to_numpy_record_array(), overwrite=overwrite)

    def get_latest_multiframe(self) -> MultiFramePayload| None:
        if not self.first_data_written:
            return None
        mf_payload = MultiFramePayload.from_numpy_record_array(mf_rec_array=self.get_latest_data())
        for frame in mf_payload.frames.values():
            frame.frame_metadata.timestamps.retrieve_from_multiframe_shm_ns = time.perf_counter_ns()

        return mf_payload

    def get_next_multiframe(self) -> MultiFramePayload:

        mf_payload = MultiFramePayload.from_numpy_record_array(mf_rec_array=self.get_latest_data())
        for frame in mf_payload.frames.values():
            frame.frame_metadata.timestamps.retrieve_from_multiframe_shm_ns = time.perf_counter_ns()
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

