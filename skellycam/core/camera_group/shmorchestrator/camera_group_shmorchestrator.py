import logging

from pydantic import BaseModel

from skellycam.app.app_state import IPCFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.camera_group.shmorchestrator.camera_shared_memory_manager import CameraGroupSharedMemory, CameraGroupSharedMemoryDTO

logger = logging.getLogger(__name__)


class CameraGroupSharedMemoryOrchestratorDTO(BaseModel):
    camera_group_shm_dto: CameraGroupSharedMemoryDTO
    camera_group_orchestrator: CameraGroupOrchestrator


class CameraGroupSharedMemoryOrchestrator(BaseModel):
    camera_group_shm: CameraGroupSharedMemory
    camera_group_orchestrator: CameraGroupOrchestrator
    read_only: bool  # whether this instance of the schmorestrator is read only

    @classmethod
    def create(cls,
               camera_configs: CameraConfigs,
               ipc_flags: IPCFlags,
               read_only: bool):
        camera_group_shm = CameraGroupSharedMemory.create(camera_configs=camera_configs, read_only=read_only)

        camera_group_orchestrator = CameraGroupOrchestrator.create(camera_configs=camera_configs,
                                                                   camera_group_shm=camera_group_shm,
                                                                   kill_camera_group_flag=ipc_flags.kill_camera_group_flag,
                                                                   global_kill_flag=ipc_flags.global_kill_flag)
        return cls(camera_configs=camera_configs,
                   camera_group_shm=camera_group_shm,
                   camera_group_orchestrator=camera_group_orchestrator,
                   ipc_flags=ipc_flags)

    @classmethod
    def recreate(cls,
                 dto: CameraGroupSharedMemoryOrchestratorDTO,
                 read_only: bool):
        return cls(
            camera_group_shm=CameraGroupSharedMemory.recreate(dto=dto.camera_group_shm_dto,
                                                              read_only=read_only),
            camera_group_orchestrator=dto.camera_group_orchestrator
        )

    def to_dto(self) -> CameraGroupSharedMemoryOrchestratorDTO:
        return CameraGroupSharedMemoryOrchestratorDTO(camera_group_shm_dto=self.camera_group_shm.to_dto(),
                                                      camera_group_orchestrator=self.camera_group_orchestrator)

    def close(self):
        logger.debug("Closing CameraGroupSharedMemoryOrchestrator...")
        self.camera_group_orchestrator.close()
        self.camera_group_shm.close_and_unlink()
