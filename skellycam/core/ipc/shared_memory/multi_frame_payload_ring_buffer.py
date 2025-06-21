import logging
import time

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.time_unit_conversion import ns_to_ms

logger = logging.getLogger(__name__)



class MultiFrameSharedMemoryRingBuffer(SharedMemoryRingBuffer):
    @classmethod
    def from_configs(cls,
                    camera_configs: CameraConfigs,
                     timebase_mapping: TimebaseMapping,
                    read_only: bool = False) -> "MultiFrameSharedMemoryRingBuffer":
        return cls.create(
            example_data=MultiFramePayload.create_dummy(camera_configs=camera_configs,
                                                        timebase_mapping=timebase_mapping).to_numpy_record_array(),
            read_only=read_only,
        )

    def put_multiframe(self,
                       mf_rec_array: np.recarray,
                       overwrite: bool) -> None:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot write to it!")
        if self.read_only:
            raise ValueError("Cannot write to read-only shared memory!")
        mf_numbers: list[int] = []
        for camera_id in mf_rec_array.dtype.names:
            mf_rec_array[camera_id].frame_metadata.timestamps.pre_copy_to_multiframe_shm_ns[0] = time.perf_counter_ns()
            mf_numbers.append(mf_rec_array[camera_id].frame_metadata.frame_number[0])
        tik = time.perf_counter_ns()
        self.put_data(data=mf_rec_array, overwrite=overwrite)

        if len(set(mf_numbers)) != 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {mf_numbers}, expected only one.")

        print(f"Put multi-frame {mf_numbers.pop()} to shared memory, took {ns_to_ms(time.perf_counter_ns() - tik):.3f} ms")


    def get_latest_multiframe(self, mf_rec_array:np.recarray) -> np.recarray:
        if not self.first_data_written:
            return mf_rec_array
        pre_tik = time.perf_counter_ns()
        mf_rec_array = self.get_latest_data(mf_rec_array)

        for camera_id in mf_rec_array.dtype.names:

            mf_rec_array[camera_id].frame_metadata.timestamps.post_retrieve_from_multiframe_shm_ns[0] = time.perf_counter_ns()
            mf_rec_array[camera_id].frame_metadata.timestamps.pre_retrieve_from_multiframe_shm_ns[0] = pre_tik
        return mf_rec_array
    def get_next_multiframe(self, mf_rec_array:np.recarray) -> np.recarray:
        pre_tik = time.perf_counter_ns()

        mf_rec_array = self.get_next_data(mf_rec_array)

        for camera_id in mf_rec_array.dtype.names:
            mf_rec_array[camera_id].frame_metadata.timestamps.post_retrieve_from_multiframe_shm_ns[0] = time.perf_counter_ns()
            mf_rec_array[camera_id].frame_metadata.timestamps.pre_retrieve_from_multiframe_shm_ns[0] = pre_tik
        return mf_rec_array

    def get_all_new_multiframes(self,mf_rec_array:np.recarray) -> list[np.recarray]:
        """
        Retrieves all new multi-frames from the shared memory.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        mfs: list[np.recarray] = []
        new_data_indicies = self.new_data_indicies
        for _ in new_data_indicies:
            og_rec_array = mf_rec_array.copy()
            mf_rec_array = self.get_next_multiframe(mf_rec_array=mf_rec_array)
            if not np.array_equal(og_rec_array, mf_rec_array):
                mfs.append(mf_rec_array.copy())
        return mfs

