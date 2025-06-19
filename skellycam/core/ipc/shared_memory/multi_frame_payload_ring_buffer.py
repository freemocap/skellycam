import logging
import time
from memory_profiler import profile
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer

logger = logging.getLogger(__name__)



class MultiFrameSharedMemoryRingBuffer(SharedMemoryRingBuffer):
    local_mfs: dict[str, MultiFramePayload]|None = None #for local cache of multi-frames, not shared between instances!
    @classmethod
    def from_configs(cls,
                    camera_configs: CameraConfigs,
                    read_only: bool = False) -> "MultiFrameSharedMemoryRingBuffer":
        instance =  cls.create(
            example_data=MultiFramePayload.create_dummy(camera_configs=camera_configs).to_numpy_record_array(),
            read_only=read_only,
        )
        instance.local_mfs = {index: MultiFramePayload.create_empty(camera_configs=camera_configs)
                              for index in range(instance.ring_buffer_length)}
        return instance

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
        mf_rec_array = self.get_latest_data()
        mf_payload = MultiFramePayload.from_numpy_record_array(mf_rec_array)
        for frame in mf_payload.frames.values():
            frame.frame_metadata.timestamps.retrieve_from_multiframe_shm_ns = time.perf_counter_ns()

        return mf_payload

    def get_next_multiframe(self) -> MultiFramePayload|None:
        mf_rec_array = self.get_next_data()
        mf_payload = MultiFramePayload.from_numpy_record_array(mf_rec_array=mf_rec_array)
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
        new_data_indicies = self.new_data_indicies
        for _ in new_data_indicies:
            mf_payload = self.get_next_multiframe()
            if mf_payload is not None:
                mfs.append(mf_payload)
        return mfs

