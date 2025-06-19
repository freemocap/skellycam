import logging
import time
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer

logger = logging.getLogger(__name__)



class MultiFrameSharedMemoryRingBuffer(SharedMemoryRingBuffer):
    @classmethod
    def from_configs(cls,
                    camera_configs: CameraConfigs,
                    read_only: bool = False) -> "MultiFrameSharedMemoryRingBuffer":
        return cls.create(
            example_data=MultiFramePayload.create_dummy(camera_configs=camera_configs).to_numpy_record_array(),
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
            frame.frame_metadata.timestamps.pre_copy_to_multiframe_shm_ns = time.perf_counter_ns()

        self.put_data(data=mf_payload.to_numpy_record_array(), overwrite=overwrite)


    def get_latest_multiframe(self, mf:MultiFramePayload|None, apply_config_rotation:bool) -> MultiFramePayload| None:
        if not self.first_data_written:
            return None
        pre_tik = time.perf_counter_ns()
        mf_rec_array = self.get_latest_data()
        if mf is None:
            mf = MultiFramePayload.from_numpy_record_array(mf_rec_array)
        else:
            mf.update_from_numpy_record_array(mf_rec_array, apply_config_rotation=apply_config_rotation)
        for frame in mf.frames.values():
            frame.frame_metadata.timestamps.post_retrieve_from_multiframe_shm_ns = time.perf_counter_ns()
            frame.frame_metadata.timestamps.pre_retrieve_from_multiframe_shm_ns = pre_tik

        return mf

    def get_next_multiframe(self, mf:MultiFramePayload|None, apply_config_rotation:bool) -> MultiFramePayload|None:
        pre_tik = time.perf_counter_ns()

        mf_rec_array = self.get_next_data()
        if mf is None:
            mf = MultiFramePayload.from_numpy_record_array(mf_rec_array=mf_rec_array)
        else:
            mf.update_from_numpy_record_array(mf_rec_array=mf_rec_array,
                                              apply_config_rotation=apply_config_rotation)
        for frame in mf.frames.values():
            frame.frame_metadata.timestamps.post_retrieve_from_multiframe_shm_ns = time.perf_counter_ns()
            frame.frame_metadata.timestamps.pre_retrieve_from_multiframe_shm_ns = pre_tik
        return mf

    def get_all_new_multiframes(self,mf:MultiFramePayload|None, apply_config_rotation:bool) -> list[MultiFramePayload]:
        """
        Retrieves all new multi-frames from the shared memory.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        mfs: list[MultiFramePayload] = []
        new_data_indicies = self.new_data_indicies
        for _ in new_data_indicies:
            mf_payload = self.get_next_multiframe(mf=mf, apply_config_rotation=apply_config_rotation)
            if mf_payload is not None:
                mfs.append(mf_payload)
        return mfs

