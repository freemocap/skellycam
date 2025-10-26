import logging
from copy import copy
from dataclasses import dataclass, field

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)

CameraSharedMemoryDTOs = dict[CameraIdString, SharedMemoryRingBufferDTO]


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_shm_dtos: CameraSharedMemoryDTOs
    camera_configs: CameraConfigs


@dataclass
class CameraGroupSharedMemory:
    camera_shms: dict[CameraIdString, CameraSharedMemoryRingBuffer]
    camera_configs: CameraConfigs
    read_only: bool
    original: bool = False
    _latest_frames: dict[CameraIdString, np.recarray] = field(default_factory=dict)

    @property
    def latest_multiframe_number(self) -> int:
        return min([camera_shared_memory.latest_frame_number for camera_shared_memory in self.camera_shms.values()])

    def get_latest_multiframe_number(self) -> int:
        return min([camera_shared_memory.latest_frame_number for camera_shared_memory in self.camera_shms.values()])

    @property
    def valid(self) -> bool:
        """
        Check if all cameras are ready and the shared memory is valid.
        """
        return all([
            all([camera_shared_memory.valid for camera_shared_memory in self.camera_shms.values()]),
        ])

    @valid.setter
    def valid(self, value: bool):
        """
        Set the validity of the shared memory.
        This is used to invalidate the shared memory when it is no longer valid.
        """
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.valid = value

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               timebase_mapping: TimebaseMapping,
               read_only: bool = False):
        validate_camera_configs(camera_configs)
        return cls(camera_shms={camera_id: CameraSharedMemoryRingBuffer.from_config(camera_config=config,
                                                                                    timebase_mapping=timebase_mapping,
                                                                                    read_only=read_only)
                                for camera_id, config in camera_configs.items()},

                   camera_configs=camera_configs,
                   original=True,
                   read_only=read_only,
                   )

    @classmethod
    def recreate(cls,
                 shm_dto: CameraGroupSharedMemoryDTO,
                 read_only: bool):

        return cls(
            camera_shms={camera_id: CameraSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                          read_only=read_only)
                         for camera_id, camera_shm_dto in shm_dto.camera_shm_dtos.items()},

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
    def new_multi_frame_available(self) -> bool:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return all([camera_shared_memory.new_frame_available
                    for camera_shared_memory in self.camera_shms.values()])

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_shm_dtos=self.camera_shm_dtos,
                                          camera_configs=self.camera_configs
                                          )


    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        if not self.original:
            raise RuntimeError(
                "Cannot unlink a non-original shared memory instance! Close child instances and unlink from the original instance instead.")
        self.valid = False
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()

    def unlink_and_close(self):
        try:
            if self.original:
                self.unlink()
            self.close()
        except Exception as e:
            logger.error(f"Error during shared memory cleanup: {type(e).__name__} - {e}")
            logger.exception(e)

    def get_latest_multiframe(self) -> dict[CameraIdString, np.recarray]|None:
        target_frame_number = copy(self.latest_multiframe_number) #copy to avoid index changing during read loop
        if target_frame_number < 0:
            return None
        self._latest_frames = {
            camera_id: camera_shared_memory.get_data_by_index(index=target_frame_number,
                                                            rec_array=self._latest_frames[camera_id] if camera_id in self._latest_frames else None)
            for camera_id, camera_shared_memory in self.camera_shms.items()
        }
        frame_numbers = set([frame.frame_metadata.frame_number[0] for frame in self._latest_frames.values()])
        if len(frame_numbers) != 1:
            raise ValueError(f"Frame numbers do not match across cameras! {frame_numbers}")
        return self._latest_frames

    def get_images_by_frame_number(self, frame_number: int, frame_recarrays:dict[CameraIdString, np.recarray]|None) -> dict[CameraIdString, np.recarray]:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        if not frame_recarrays:
            frame_recarrays = {camera_id: None for camera_id in self.camera_shms.keys()}

        for camera_id, camera_shared_memory in self.camera_shms.items():
            frame_recarrays[camera_id] = camera_shared_memory.get_data_by_index(index=frame_number,
                                                                               rec_array=frame_recarrays[camera_id])
        return frame_recarrays
