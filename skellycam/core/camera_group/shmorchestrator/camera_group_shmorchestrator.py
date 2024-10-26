import logging

from pydantic import BaseModel, ConfigDict

from skellycam.app.app_controller.ipc_flags import IPCFlags
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_group_shared_memory import \
    SingleSlotCameraGroupSharedMemoryDTO, SingleSlotCameraGroupSharedMemory

logger = logging.getLogger(__name__)


class CameraGroupSharedMemoryOrchestratorDTO(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    camera_group_shm_dto: SingleSlotCameraGroupSharedMemoryDTO
    camera_group_orchestrator: CameraGroupOrchestrator


class CameraGroupSharedMemoryOrchestrator(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    shm: SingleSlotCameraGroupSharedMemory
    orchestrator: CameraGroupOrchestrator

    @classmethod
    def create(cls,
               camera_group_dto: CameraGroupDTO,
               ipc_flags: IPCFlags,
               read_only: bool):
        return cls(shm=SingleSlotCameraGroupSharedMemory.create(camera_group_dto=camera_group_dto,
                                                                read_only=read_only),
                   orchestrator=CameraGroupOrchestrator.create(camera_group_dto=camera_group_dto,
                                                               ipc_flags=ipc_flags)
                   )

    @classmethod
    def recreate(cls,
                 camera_group_dto: CameraGroupDTO,
                 shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                 read_only: bool):
        return cls(
            shm=SingleSlotCameraGroupSharedMemory.recreate(camera_group_dto=camera_group_dto,
                                                           shm_dto=shmorc_dto.camera_group_shm_dto,
                                                           read_only=read_only),
            orchestrator=shmorc_dto.camera_group_orchestrator,
        )

    @property
    def valid(self):
        return self.shm.valid

    def to_dto(self) -> CameraGroupSharedMemoryOrchestratorDTO:
        return CameraGroupSharedMemoryOrchestratorDTO(camera_group_shm_dto=self.shm.to_dto(),
                                                      camera_group_orchestrator=self.orchestrator)

    def close_and_unlink(self):
        logger.debug("Closing CameraGroupSharedMemoryOrchestrator...")
        self.orchestrator.pause_loop()
        self.shm.close_and_unlink()
