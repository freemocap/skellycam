import logging
import multiprocessing
from multiprocessing import Process

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera.config.update_instructions import UpdateInstructions
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.camera_manager import CameraManager
from skellycam.core.camera_group.frame_wrangler import FrameWrangler
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestratorDTO

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(self, camera_group_dto: CameraGroupDTO, shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO):
        self.frame_wrangler_config_queue = multiprocessing.Queue()
        self.dto = camera_group_dto
        self._process = Process(
            name=self.__class__.__name__,
            target=self._run_process,
            args=(camera_group_dto,
                  shmorc_dto,
                  self.frame_wrangler_config_queue
                  )
        )

    @property
    def camera_ids(self) -> list[CameraId]:
        return list(self.dto.camera_configs.keys())

    @property
    def camera_configs(self) -> CameraConfigs:
        return self.dto.camera_configs

    @property
    def uuid(self) -> str:
        return self.dto.group_uuid

    def start(self):
        logger.info("Starting camera group")
        self._process.start()

    def close(self):
        logger.debug("Closing camera group")
        self.dto.ipc_flags.kill_camera_group_flag.value = True
        self._process.join()
        logger.info("Camera group closed.")

    def update_camera_configs(self,
                              camera_configs: CameraConfigs,
                              update_instructions: UpdateInstructions):
        logger.debug(
            f"Updating Camera Configs with instructions: {update_instructions}")
        self.dto.camera_configs = camera_configs
        self.dto.config_update_queue.put(update_instructions)
        self.frame_wrangler_config_queue.put(update_instructions.new_configs)

    @staticmethod
    def _run_process(camera_group_dto: CameraGroupDTO,
                     shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                     new_configs_queue: multiprocessing.Queue):
        logger.debug(f"CameraGroupProcess started")

        frame_wrangler = FrameWrangler(camera_group_dto=camera_group_dto,
                                       shmorc_dto=shmorc_dto,
                                        new_configs_queue=new_configs_queue)

        camera_manager = CameraManager.create(camera_group_dto=camera_group_dto,
                                              shmorc_dto=shmorc_dto)

        try:
            frame_wrangler.start()
            camera_manager.start() # blocks until cameras close

        except Exception as e:
            logger.error(f"CameraGroupProcess error: {e}")
            logger.exception(e)
            raise
        finally:
            camera_group_dto.ipc_flags.kill_camera_group_flag.value = True
            camera_manager.join()
            frame_wrangler.join()
            logger.debug(f"CameraGroupProcess completed")



