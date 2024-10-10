import logging
import multiprocessing
from multiprocessing import Process
from typing import Optional

from pydantic import BaseModel, ConfigDict

from skellycam.app.app_state import IPCFlags
from skellycam.core.camera_group.camera.camera_manager import CameraManager
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler

logger = logging.getLogger(__name__)

class CameraGroupDTO(BaseModel):
    camera_configs: CameraConfigs
    shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO
    ipc_queue: multiprocessing.Queue
    config_update_queue = multiprocessing.Queue()  # Update camera configs

    ipc_flags: IPCFlags
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    @property
    def camera_ids(self):
        return list(self.camera_configs.keys())

class CameraGroupProcess:
    def __init__(
            self,
            dto: CameraGroupDTO,
    ):
        self._dto = dto
        self._process = Process(
            name=CameraGroupProcess.__name__,
            target=CameraGroupProcess._run_process,
            args=dto
        )

    @property
    def process(self):
        return self._process

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    async def start(self):
        logger.debug("Starting `CameraGroupProcess`...")
        self._process.start()

    async def close(self):
        logger.debug("Closing `CameraGroupProcess`...")
        self._dto.kill_camera_group_flag.value = True
        self._process.join()
        logger.debug("CameraGroupProcess closed.")

    @staticmethod
    def _run_process(dto: CameraGroupDTO):
        logger.debug(f"CameraGroupProcess started")

        frame_wrangler = FrameWrangler.from_camera_group_dto(dto)
        camera_manager = CameraManager.from_camera_group_dto(dto)

        try:
            frame_wrangler.start()
            camera_manager.start()

        except Exception as e:
            logger.error(f"CameraGroupProcess error: {e}")
            logger.exception(e)
            raise
        finally:
            dto.ipc_flags.kill_camera_group_flag.value = True
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            logger.debug(f"CameraGroupProcess completed")


class CameraGroup(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dto: CameraGroupDTO
    camera_group_process: Optional[CameraGroupProcess] = None

    @classmethod
    def create(cls, dto: CameraGroupDTO):
        return cls(dto=dto, camera_group_process=CameraGroupProcess(dto=dto))


    async def start(self, number_of_frames: Optional[int] = None):
        logger.info("Starting camera group")
        await self.camera_group_process.start()

    async def close(self):
        logger.debug("Closing camera group")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        if self.camera_group_process:
            await self.camera_group_process.close()
        logger.info("Camera group closed.")

    async def update_camera_configs(self,
                                    camera_configs: CameraConfigs,
                                    update_instructions: UpdateInstructions):
        logger.debug(
            f"Updating Camera Configs with instructions: {update_instructions}")
        self._dto.camera_configs = camera_configs
        self._dto.config_update_que.put(update_instructions)

