import logging
import multiprocessing
from multiprocessing import Process

from skellycam.core.cameras.camera.camera_manager import CameraManager
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO

logger = logging.getLogger(__name__)


class CameraGroupProcess:
    def __init__(
            self,
            group_shm_dto: CameraGroupSharedMemoryDTO,
            shm_valid_flag: multiprocessing.Value,
            config_update_queue: multiprocessing.Queue,
            ipc_queue: multiprocessing.Queue,
            camera_configs: CameraConfigs,
            record_frames_flag: multiprocessing.Value,
            kill_camera_group_flag: multiprocessing.Value,
            global_kill_event: multiprocessing.Event,
    ):
        self._kill_camera_group_flag = kill_camera_group_flag
        self._process = Process(
            name=CameraGroupProcess.__name__,
            target=CameraGroupProcess._run_process,
            args=(group_shm_dto,
                  shm_valid_flag,
                  config_update_queue,
                  ipc_queue,
                  camera_configs,
                  record_frames_flag,
                  self._kill_camera_group_flag,
                  global_kill_event,
                  )
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
        self._kill_camera_group_flag.value = True
        self._process.join()
        logger.debug("CameraGroupProcess closed.")

    @staticmethod
    def _run_process(group_shm_dto: CameraGroupSharedMemoryDTO,
                     shm_valid_flag: multiprocessing.Value,
                     config_update_queue: multiprocessing.Queue,
                     ipc_queue: multiprocessing.Queue,
                     camera_configs: CameraConfigs,
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     global_kill_event: multiprocessing.Event
                     ):
        logger.debug(f"CameraGroupProcess started")

        # TODO - Move up and make DTO's to build these whacky sub-processes
        group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs,
                                                                         kill_camera_group_flag=kill_camera_group_flag,
                                                                         global_kill_event=global_kill_event)

        frame_wrangler = FrameWrangler(group_shm_dto=group_shm_dto,
                                       shm_valid_flag=shm_valid_flag,
                                       group_orchestrator=group_orchestrator,
                                       ipc_queue=ipc_queue,
                                       record_frames_flag=record_frames_flag,
                                       kill_camera_group_flag=kill_camera_group_flag,
                                       global_kill_event=global_kill_event,
                                       )
        camera_manager = CameraManager(group_shm_dto=group_shm_dto,
                                       shm_valid_flag=shm_valid_flag,
                                       group_orchestrator=group_orchestrator,
                                       kill_camera_group_flag=kill_camera_group_flag,
                                       global_kill_event=global_kill_event,
                                       )

        try:

            frame_wrangler.start()

            camera_group_trigger_loop(
                camera_configs=camera_configs,
                group_orchestrator=group_orchestrator,
                camera_manager=camera_manager,
                config_update_queue=config_update_queue,
                kill_camera_group_flag=kill_camera_group_flag,
                global_kill_event=global_kill_event,
            )


        except Exception as e:
            logger.error(f"CameraGroupProcess error: {e}")
            logger.exception(e)
            raise
        finally:
            kill_camera_group_flag.value = True
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            logger.debug(f"CameraGroupProcess completed")
