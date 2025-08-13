import logging
from dataclasses import dataclass

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.multi_frame_payload_ring_buffer import MultiFrameSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElementDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber
from skellycam.core.recorders.framerate_tracker import FramerateTracker
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)

CameraSharedMemoryDTOs = dict[CameraIdString, SharedMemoryRingBufferDTO]


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_shm_dtos: CameraSharedMemoryDTOs
    multi_frame_ring_shm_dto: SharedMemoryRingBufferDTO
    camera_configs: CameraConfigs


@dataclass
class CameraGroupSharedMemoryManager:
    camera_shms: dict[CameraIdString, FramePayloadSharedMemoryRingBuffer]
    multi_frame_ring_shm: MultiFrameSharedMemoryRingBuffer
    camera_configs: CameraConfigs
    read_only: bool
    original: bool = False

    @property
    def valid(self) -> bool:
        """
        Check if all cameras are ready and the shared memory is valid.
        """
        return all([
            all([camera_shared_memory.valid for camera_shared_memory in self.camera_shms.values()]),
            self.multi_frame_ring_shm.valid,
        ])

    @valid.setter
    def valid(self, value: bool):
        """
        Set the validity of the shared memory.
        This is used to invalidate the shared memory when it is no longer valid.
        """
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.valid = value
        self.multi_frame_ring_shm.valid = value

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               timebase_mapping: TimebaseMapping,
               read_only: bool = False):
        validate_camera_configs(camera_configs)
        return cls(camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.from_config(camera_config=config,
                                                                                          timebase_mapping=timebase_mapping,
                                                                                          read_only=read_only)
                                for camera_id, config in camera_configs.items()},

                   multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.from_configs(
                       timebase_mapping=timebase_mapping,
                       camera_configs=camera_configs,
                       read_only=read_only),
                   camera_configs=camera_configs,
                   original=True,
                   read_only=read_only,
                   )

    @classmethod
    def recreate(cls,
                 shm_dto: CameraGroupSharedMemoryDTO,
                 read_only: bool):

        return cls(
            camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                                read_only=read_only)
                         for camera_id, camera_shm_dto in shm_dto.camera_shm_dtos.items()},
            multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.recreate(
                dto=shm_dto.multi_frame_ring_shm_dto,
                read_only=read_only),
            camera_configs=shm_dto.camera_configs,
            read_only=read_only)

    @property
    def camera_shm_dtos(self) -> CameraSharedMemoryDTOs:
        return {camera_id: camera_shared_memory.to_dto() for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_shms.keys())

    @property
    def latest_mf_available(self) -> int:
        """
        Returns the latest multi-frame number available in the shared memory.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return self.multi_frame_ring_shm.last_written_index.value

    @property
    def latest_frame_number_available_by_camera(self) -> dict[CameraIdString, int]:
        """
        Returns a dictionary mapping camera IDs to the latest frame number available in each camera's shared memory.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return {camera_id: camera_shared_memory.latest_frame_number
                for camera_id, camera_shared_memory in self.camera_shms.items()}

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_shm_dtos=self.camera_shm_dtos,
                                          multi_frame_ring_shm_dto=self.multi_frame_ring_shm.to_dto(),
                                          camera_configs=self.camera_configs
                                          )


    def _build_multi_frame_payload_by_number(self, mf_rec_array: np.recarray, target_mf_number: int) -> tuple[np.recarray, int]:
        """
        Retrieves the latest frame from each camera shm and copies it to the MultiFrameSharedMemoryRingBuffer.
        """
        if self.read_only:
            raise ValueError(
                "Cannot use `get_next_multi_frame_payload` in read-only mode - use `get_latest_multi_frame_payload` instead!")
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

        for camera_id, camera_shared_memory in self.camera_shms.items():
            if not camera_shared_memory.new_frame_available:
                raise ValueError(f"Camera {camera_id} does not have a new frame available!")
            mf_rec_array[camera_id] = camera_shared_memory.get_data_by_index(rec_array=mf_rec_array[camera_id],
                                                                             index=target_mf_number)
            if mf_rec_array[camera_id].frame_metadata.frame_number[0] != target_mf_number:
                raise ValueError(
                    f"Frame number mismatch! Expected {target_mf_number}, got {mf_rec_array[camera_id].frame_metadata.frame_number[0]}")

        return self._validate_and_copy_out_multiframe(mf_rec_array=mf_rec_array,
                                                        target_mf_number=target_mf_number)

    def _validate_and_copy_out_multiframe(self, mf_rec_array: np.recarray, target_mf_number:int) -> tuple[np.recarray, int]:

        self.multi_frame_ring_shm.put_multiframe(mf_rec_array=mf_rec_array,
                                                 overwrite_allowed=False)  # Don't overwrite to ensure all frames are saved

        mf_numbers = set(mf_rec_array[camera_id].frame_metadata.frame_number[0] for camera_id in self.camera_ids)
        if len(mf_numbers) > 1:
            raise ValueError(f"Multi-frame payload has multiple frame numbers: {mf_numbers}. "
                             f"Expected all cameras to have the same frame number.")
        latest_read_mf_number = mf_numbers.pop()
        if not latest_read_mf_number == target_mf_number:
            raise ValueError(f"Multi-frame payload has frame number {latest_read_mf_number}, "
                             f"but requested frame number was {target_mf_number}.")

        return mf_rec_array, latest_read_mf_number


    def build_multiframe_by_number(self, mf_rec_array: np.recarray, target_mf_number: int,
                                   framerate_tracker: FramerateTracker) -> tuple[
        np.recarray, int, FramerateTracker]:
        mf_rec_array, read_mf_number = self._build_multi_frame_payload_by_number(mf_rec_array=mf_rec_array,
                                                                                 target_mf_number=target_mf_number)
        ts = []
        for camera_id in mf_rec_array.dtype.names:
            ts.append(np.mean([mf_rec_array[camera_id].frame_metadata.timestamps.pre_frame_grab_ns,
                               mf_rec_array[camera_id].frame_metadata.timestamps.post_frame_grab_ns]))
        framerate_tracker.update(timestamp_ns=float(np.mean(ts)))

        return mf_rec_array, read_mf_number, framerate_tracker  # recycle the mf object to save memory

    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()
        self.multi_frame_ring_shm.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        if not self.original:
            raise RuntimeError(
                "Cannot unlink a non-original shared memory instance! Close child instances and unlink from the original instance instead.")
        self.valid = False
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()
        self.multi_frame_ring_shm.unlink()

    def unlink_and_close(self):
        try:
            if self.original:
                self.unlink()
            self.close()
        except Exception as e:
            logger.error(f"Error during shared memory cleanup: {type(e).__name__} - {e}")
            logger.exception(e)
