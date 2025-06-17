import logging
from dataclasses import dataclass

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.multi_frame_payload_ring_buffer import MultiFrameSharedMemoryRingBuffer
from skellycam.core.ipc.shared_memory.multi_frame_payload_single_slot_shared_memory import \
    MultiframePayloadSingleSlotSharedMemory
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBufferDTO
from skellycam.core.ipc.shared_memory.shared_memory_element import SharedMemoryElementDTO
from skellycam.core.ipc.shared_memory.shared_memory_number import SharedMemoryNumber
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
    _latest_mf_built: int = -1  # Used to track the latest multi-frame number built in THIS process, not shared memory


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

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               read_only: bool = False):
        return cls(camera_shms={camera_id: FramePayloadSharedMemoryRingBuffer.from_config(camera_config=config,
                                                                                          read_only=read_only)
                                for camera_id, config in camera_configs.items()},

                   multi_frame_ring_shm=MultiFrameSharedMemoryRingBuffer.from_configs(
                       camera_configs=camera_configs,
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
    def new_multi_frame_available(self) -> bool:
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        return all([camera_shared_memory.new_frame_available
                    for camera_shared_memory in self.camera_shms.values()])

    def to_dto(self) -> CameraGroupSharedMemoryDTO:
        return CameraGroupSharedMemoryDTO(camera_shm_dtos=self.camera_shm_dtos,
                                          multi_frame_ring_shm_dto=self.multi_frame_ring_shm.to_dto(),
                                            camera_configs=self.camera_configs
                                          )

    def build_next_multi_frame_payload(self) -> MultiFramePayload:
        """
        Retrieves the latest frame from each camera shm and copies it to the MultiFrameSharedMemoryRingBuffer.
        """
        if self.read_only:
            raise ValueError(
                "Cannot use `get_next_multi_frame_payload` in read-only mode - use `get_latest_multi_frame_payload` instead!")
        if not self.valid:
            raise ValueError("Shared memory instance has been invalidated, cannot read from it!")
        mf_payload: MultiFramePayload = MultiFramePayload.create_empty(camera_configs=self.camera_configs)


        for camera_id, camera_shared_memory in self.camera_shms.items():
            if not camera_shared_memory.new_frame_available:
                raise ValueError(f"Camera {camera_id} does not have a new frame available!")

            frame = camera_shared_memory.retrieve_next_frame()
            if frame.frame_number != self._latest_mf_built + 1:
                raise ValueError(
                    f"Frame number mismatch! Expected {self._latest_mf_built + 1}, got {frame.frame_number}")
            mf_payload.add_frame(frame)
        if not mf_payload or not mf_payload.full:
            raise ValueError("Did not read full multi-frame mf_payload!")
        self.multi_frame_ring_shm.put_multiframe(mf_payload=mf_payload,
                                                 overwrite=False)  # Don't overwrite to ensure all frames are saved
        self._latest_mf_built = mf_payload.multi_frame_number
        logger.loop(f"Built multiframe #{mf_payload.multi_frame_number} from cameras: {list(mf_payload.camera_ids)}")

        return mf_payload

    def build_all_new_multiframes(self) -> list[MultiFramePayload]:
        mfs: list[MultiFramePayload] = []
        while self.new_multi_frame_available:
            mf_payload = self.build_next_multi_frame_payload()
            mfs.append(mf_payload)
        return mfs

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
        self.unlink()
        self.close()
