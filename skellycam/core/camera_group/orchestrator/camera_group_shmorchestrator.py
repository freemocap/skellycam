import logging

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.orchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.shared_memory.multi_frame_escape_ring_buffer import \
    MultiFrameEscapeSharedMemoryRingBuffer, MultiFrameEscapeSharedMemoryRingBufferDTO
from skellycam.core.shared_memory.single_slot_camera_group_shared_memory import CameraGroupSharedMemory, \
    SingleSlotCameraGroupSharedMemoryDTO

logger = logging.getLogger(__name__)


class CameraGroupSharedMemoryOrchestratorDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frame_loop_shm_dto: SingleSlotCameraGroupSharedMemoryDTO
    multi_frame_escape_shm_dto: MultiFrameEscapeSharedMemoryRingBufferDTO
    camera_group_orchestrator: CameraGroupOrchestrator


class CameraGroupSharedMemoryOrchestrator(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    camera_group_shm: CameraGroupSharedMemory
    multiframe_escape_ring_shm: MultiFrameEscapeSharedMemoryRingBuffer
    orchestrator: CameraGroupOrchestrator

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               read_only: bool):
        return cls(
            camera_group_shm=CameraGroupSharedMemory.create(camera_configs=camera_group_dto.camera_configs,
                                                            read_only=read_only),
            multiframe_escape_ring_shm=MultiFrameEscapeSharedMemoryRingBuffer.create(camera_group_dto=camera_group_dto,
                                                                                     read_only=read_only),
            orchestrator=CameraGroupOrchestrator.from_dto(camera_group_dto=camera_group_dto,)
            )

    @classmethod
    def recreate(cls,
                 camera_group_dto: CameraGroupDTO,
                 shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                 read_only: bool):
        return cls(
            camera_group_shm=CameraGroupSharedMemory.recreate(shm_dto=shmorc_dto.frame_loop_shm_dto,
                                                              read_only=read_only),
            multiframe_escape_ring_shm=MultiFrameEscapeSharedMemoryRingBuffer.recreate(camera_group_dto=camera_group_dto,
                                                                                       shm_dto=shmorc_dto.multi_frame_escape_shm_dto,
                                                                                       read_only=read_only),
            orchestrator=shmorc_dto.camera_group_orchestrator,
        )

    @property
    def valid(self):
        return self.camera_group_shm.valid and self.multiframe_escape_ring_shm.valid

    def to_dto(self) -> CameraGroupSharedMemoryOrchestratorDTO:
        return CameraGroupSharedMemoryOrchestratorDTO(frame_loop_shm_dto=self.camera_group_shm.to_dto(),
                                                      multi_frame_escape_shm_dto=self.multiframe_escape_ring_shm.to_dto(),
                                                      camera_group_orchestrator=self.orchestrator)

    def close_and_unlink(self):
        logger.debug("Closing CameraGroupSharedMemoryOrchestrator...")
        self.orchestrator.pause_loop()
        self.camera_group_shm.close_and_unlink()
        self.multiframe_escape_ring_shm.close_and_unlink()
