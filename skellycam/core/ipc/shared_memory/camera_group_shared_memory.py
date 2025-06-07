import logging
import multiprocessing
from copy import deepcopy
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer, \
    FramePayloadSharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.multi_frame_payload_ring_buffer import MultiFrameSharedMemoryRingBufferDTO, \
    MultiFrameSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.multi_frame_payload_single_slot_shared_memory import \
    MultiframePayloadSingleSlotSharedMemory, MultiframePayloadSingleSlotSharedMemoryDTO
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)

CameraSharedMemoryDTOs = dict[CameraIdString, FramePayloadSharedMemoryRingBufferDTO]


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_shm_dtos: CameraSharedMemoryDTOs
    multi_frame_ring_shm_dto: MultiFrameSharedMemoryRingBufferDTO
    latest_mf_shm_dto: MultiframePayloadSingleSlotSharedMemoryDTO
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value
    camera_configs: CameraConfigs


@dataclass
class CameraGroupSharedMemoryManager:
    camera_shms: dict[
        CameraIdString, FramePayloadSharedMemoryRingBuffer]  # where the camera processes will publish their frames
    camera_configs: CameraConfigs
    multi_frame_ring_shm: MultiFrameSharedMemoryRingBuffer  # where we will publish new multi-frame payloads
    latest_multiframe_shm: MultiframePayloadSingleSlotSharedMemory
    read_only: bool  # is this instance allowed to mutate the shm (publishing or read_next)?
    shm_valid_flag: multiprocessing.Value = multiprocessing.Value('b', True)
    latest_mf_number: multiprocessing.Value = multiprocessing.Value("l", -1)
    original: bool = False  # is this the original shared memory instance?

    @property
    def valid(self) -> bool:
        """
        Check if all cameras are ready and the shared memory is valid.
        """
        return all([
            self.shm_valid_flag.value,
            all([camera_shared_memory.valid for camera_shared_memory in self.camera_shms.values()]),
            self.multi_frame_ring_shm.valid,
            self.latest_multiframe_shm
        ])

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               read_only: bool = False):
        return cls(camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.create(camera_config=config,
                                                                                     read_only=read_only)
                                for camera_id, config in camera_configs.items()},
                   multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.create_from_configs(
                       configs=camera_configs,
                       read_only=read_only),
                   latest_multiframe_shm=MultiframePayloadSingleSlotSharedMemory.create_from_configs(
                       configs=camera_configs,
                       read_only=read_only),
                   camera_configs=camera_configs,
                   original=True,
                   read_only=read_only)

    @classmethod
    def recreate(cls,
                 shm_dto: CameraGroupSharedMemoryDTO,
                 read_only: bool):

        return cls(
            camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                                read_only=read_only)
                         for camera_id, camera_shm_dto in shm_dto.camera_shm_dtos.items()},
            multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.recreate(
                shm_dto=shm_dto.multi_frame_ring_shm_dto,
                read_only=read_only),
            latest_multiframe_shm=MultiframePayloadSingleSlotSharedMemory.recreate(
                shm_dto=shm_dto.latest_mf_shm_dto,
                read_only=read_only),
            shm_valid_flag=shm_dto.shm_valid_flag,
            latest_mf_number=shm_dto.latest_mf_number,
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
                                          multi_frame_ring_shm_dto=self.multi_frame_ring_shm.to_dto(),
                                          latest_mf_shm_dto=self.latest_multiframe_shm.to_dto(),
                                          shm_valid_flag=self.shm_valid_flag,
                                          latest_mf_number=self.latest_mf_number,
                                          camera_configs=self.camera_configs
                                          )

    def publish_next_multi_frame_payload(self,
                                         overwrite: bool,
                                         previous_payload: MultiFramePayload | None = None,
                                         ) -> MultiFramePayload:
        """
        Retrieves the latest frame from each camera shm and copies it to the MultiFrameSharedMemoryRingBuffer.
        """
        if self.read_only:
            raise ValueError(
                "Cannot use `get_next_multi_frame_payload` in read-only mode - use `get_latest_multi_frame_payload` instead!")
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        if previous_payload is None:
            mf_payload: MultiFramePayload = MultiFramePayload.create_initial(
                camera_configs=self.camera_configs)
        else:
            mf_payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                            camera_configs=dict(
                                                                                deepcopy(self.ipc.camera_configs)))

        for camera_id, camera_shared_memory in self.camera_shms.items():
            if not camera_shared_memory.new_frame_available:
                raise ValueError(f"Camera {camera_id} does not have a new frame available!")

            frame = camera_shared_memory.retrieve_next_frame()
            if frame.frame_number != self.latest_mf_number.value + 1:
                raise ValueError(
                    f"Frame number mismatch! Expected {self.latest_mf_number.value + 1}, got {frame.frame_number}")
            mf_payload.add_frame(frame)
        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        self.multi_frame_ring_shm.put_multiframe(mf_payload, overwrite=overwrite)
        self.latest_mf_number.value = mf_payload.multi_frame_number
        return mf_payload

    def publish_all_new_multiframes(self,
                                    overwrite: bool,
                                    previous_payload: MultiFramePayload | None = None) -> list[MultiFramePayload]:
        mfs: list[MultiFramePayload] = []
        while self.new_multi_frame_available:
            mf_payload = self.publish_next_multi_frame_payload(previous_payload=previous_payload,
                                                               overwrite=overwrite)
            mfs.append(mf_payload)
            previous_payload = mf_payload
        if len(mfs) > 0 and isinstance(mfs[-1], MultiFramePayload):
            self.latest_multiframe_shm.put_multiframe(mfs[-1], overwrite=overwrite)

        return mfs

    def get_next_multiframe(self) -> MultiFramePayload:
        """
        Retrieves the next multi-frame data from the shared memory.
        This method incremenets the multi-frame number, so it is NOT available for read-only instances.
        """
        if self.read_only:
            raise ValueError(
                "Cannot use `get_next_multiframe` in read-only mode - use `get_latest_multiframe` instead!")
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return self.multi_frame_ring_shm.get_next_multiframe(camera_configs=self.camera_configs)

    def get_all_new_multiframes(self, invalid_ok: bool) -> list[MultiFramePayload]:
        """
        Retrieves all new multi-frame data from the shared memory.
        This method increments the multi-frame number, so it is NOT available for read-only instances.
        """
        if self.read_only:
            raise ValueError(
                "Cannot use `get_all_new_multiframes` in read-only mode - use `get_latest_multiframe` instead!")
        if not self.valid:
            if invalid_ok:
                return []
            else:
                raise ValueError("Shared memory instance has been invalidated, and thats not ok!")
        return self.multi_frame_ring_shm.get_all_new_multiframes(camera_configs=self.camera_configs)

    def get_latest_multiframe(self, if_newer_than_mf_number: int | None = None) -> MultiFramePayload | None:
        """
        Retrieves the latest multi-frame data if it is newer than the provided multi-frame number.
        """
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        if not self.latest_multiframe_shm.first_frame_written:
            return None
        if if_newer_than_mf_number is not None and if_newer_than_mf_number >= self.latest_multiframe_shm.latest_written_mf_number.value:
            return None
        mf = self.latest_multiframe_shm.retrieve_multiframe(camera_configs=self.camera_configs)
        if if_newer_than_mf_number and mf.multi_frame_number <= if_newer_than_mf_number:
            raise ValueError(
                f"Latest multi-frame number {mf.multi_frame_number} is not newer than {if_newer_than_mf_number} - something is broken!")
        return mf

    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        self.shm_valid_flag.value = False
        if not self.original:
            raise RuntimeError(
                "Cannot unlink a non-original shared memory instance! Close child instances and unlink from the original instance instead.")
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()
