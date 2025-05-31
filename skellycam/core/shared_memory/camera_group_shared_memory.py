import logging
import multiprocessing
from dataclasses import dataclass


from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer, \
    FramePayloadSharedMemoryRingBufferDTO
from skellycam.core.shared_memory.multi_frame_payload_ring_buffer import MultiFrameSharedMemoryRingBufferDTO, \
    MultiFrameSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)

CameraSharedMemoryDTOs = dict[CameraIdString, FramePayloadSharedMemoryRingBufferDTO]


@dataclass
class CameraGroupSharedMemoryDTO:
    camera_shm_dtos: CameraSharedMemoryDTOs
    multi_frame_shm_dto: MultiFrameSharedMemoryRingBufferDTO
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value


@dataclass
class CameraGroupSharedMemory:
    camera_shms: dict[CameraIdString, FramePayloadSharedMemoryRingBuffer]
    multi_frame_shm: MultiFrameSharedMemoryRingBuffer
    shm_valid_flag: multiprocessing.Value
    latest_mf_number: multiprocessing.Value
    read_only: bool
    original:bool = False  # Used to indicate if this is the original shared memory instance

    @classmethod
    def create_from_ipc(cls,
                        camera_group_ipc: CameraGroupIPC,
                        read_only: bool = False):
        return cls(camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.create(camera_config=config,
                                                                                     read_only=read_only)
                                for camera_id, config in camera_group_ipc.camera_configs.items()},
                   multi_frame_shm=MultiFrameSharedMemoryRingBuffer.create_from_ipc(
                       ipc=camera_group_ipc,
                       read_only=read_only),
                   shm_valid_flag=multiprocessing.Value('b', True),
                   latest_mf_number=multiprocessing.Value("l", -1),
                   original=True,
                   read_only=read_only)

    @classmethod
    def recreate_from_dto(cls,
                          shm_dto: CameraGroupSharedMemoryDTO,
                          read_only: bool):

        return cls(camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                                       read_only=read_only)
                                for camera_id, camera_shm_dto in shm_dto.camera_shm_dtos.items()},
                   multi_frame_shm=MultiFrameSharedMemoryRingBuffer.recreate(
                       shm_dto=shm_dto.multi_frame_shm_dto,
                       read_only=read_only),
                   shm_valid_flag=shm_dto.shm_valid_flag,
                   latest_mf_number=shm_dto.latest_mf_number,
                   read_only=read_only)

    @property
    def camera_shm_dtos(self) -> CameraSharedMemoryDTOs:
        return {camera_id: camera_shared_memory.to_dto() for camera_id, camera_shared_memory in
                self.camera_shms.items()}

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_shms.keys())

    @property
    def valid(self) -> bool:
        return self.shm_valid_flag.value

    @property
    def new_multi_frame_available(self) -> bool:
        if not self.valid:
            return False
        return all([camera_shared_memory.new_frame_available
                    for camera_shared_memory in self.camera_shms.values()])

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_shm_dtos=self.camera_shm_dtos,
                                          multi_frame_shm_dto=self.multi_frame_shm.to_dto(),
                                          shm_valid_flag=self.shm_valid_flag,
                                          latest_mf_number=self.latest_mf_number)

    def get_next_multi_frame_payload(self,
                                     camera_configs: CameraConfigs| None = None,
                                     previous_payload: MultiFramePayload | None = None,
                                     ) -> MultiFramePayload:
        if self.read_only:
            raise ValueError(
                "Cannot use `get_next_multi_frame_payload` in read-only mode - use `get_latest_multi_frame_payload` instead!")
        if previous_payload is None:
            if camera_configs is None:
                raise ValueError("Camera configs must be provided if no previous payload is given!")
            mf_payload: MultiFramePayload = MultiFramePayload.create_initial(camera_configs=camera_configs)
        else:
            mf_payload: MultiFramePayload = MultiFramePayload.from_previous(previous=previous_payload,
                                                                            camera_configs=camera_configs)

        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")

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
        if not self.read_only:
            self.latest_mf_number.value = mf_payload.multi_frame_number
        return mf_payload

    def get_all_new_frames(self, previous_payload: MultiFramePayload) -> list[MultiFramePayload]:
        mfs:list[MultiFramePayload] = []
        while self.new_multi_frame_available:
            mf_payload = self.get_next_multi_frame_payload(previous_payload=previous_payload)
            mfs.append(mf_payload)
            previous_payload = mf_payload
        return mfs

    def close(self):
        # Close this process's access to the shared memory, but other processes can still access it
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.close()

    def unlink(self):
        # Unlink the shared memory so that it is removed from the system, memory becomes invalid for all processes
        self.shm_valid_flag.value = False
        if not self.original:
            raise RuntimeError("Cannot unlink a non-original shared memory instance! Close child instances and unlink from the original instance instead.")
        for camera_shared_memory in self.camera_shms.values():
            camera_shared_memory.unlink()

    def close_and_unlink(self):
        self.close()
        self.unlink()


