import logging
import multiprocessing
import threading
from multiprocessing import Process
from typing import Optional

from skellycam.api.app.app_state import get_app_state, AppState
from skellycam.core.cameras.camera.camera_manager import CameraManager
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.cameras.group.update_instructions import UpdateInstructions
from skellycam.core.frames.frame_wrangler import FrameWrangler
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_1s

logger = logging.getLogger(__name__)


class CameraGroupProcess:
    def __init__(
            self,
            frontend_pipe: multiprocessing.Pipe,
            config_update_queue: multiprocessing.Queue,
            ipc_queue: multiprocessing.Queue,
    ):
        app_state: AppState = get_app_state()
        self._process = Process(
            name=CameraGroupProcess.__name__,
            target=CameraGroupProcess._run_process,
            args=(frontend_pipe,
                  config_update_queue,
                  ipc_queue,
                  app_state.camera_configs,
                  app_state.record_frames_flag,
                  app_state.kill_camera_group_flag
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
        get_app_state().kill_camera_group_flag.value = True
        self._process.join()
        logger.debug("CameraGroupProcess closed.")

    @staticmethod
    def _run_process(frontend_pipe: multiprocessing.Pipe,
                     config_update_queue: multiprocessing.Queue,
                     ipc_queue: multiprocessing.Queue,
                     camera_configs: CameraConfigs,
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.debug(f"CameraGroupProcess started")
        camera_manager: Optional[CameraManager] = None
        group_shm: Optional[CameraGroupSharedMemory] = None
        frame_wrangler: Optional[FrameWrangler] = None
        try:
            while not kill_camera_group_flag.value:
                group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs,
                                                                                 kill_camera_group_flag=kill_camera_group_flag)

                group_shm = CameraGroupSharedMemory.create(camera_configs=camera_configs)

                frame_wrangler = FrameWrangler(camera_configs=camera_configs,
                                               group_shm_names=group_shm.shared_memory_names,
                                               group_orchestrator=group_orchestrator,
                                               frontend_pipe=frontend_pipe,
                                               update_queue=config_update_queue,
                                               ipc_queue=ipc_queue,
                                               record_frames_flag=record_frames_flag,
                                               kill_camera_group_flag=kill_camera_group_flag,
                                               )
                camera_manager = CameraManager(camera_configs=camera_configs,
                                               shared_memory_names=group_shm.shared_memory_names,
                                               group_orchestrator=group_orchestrator,
                                               ipc_queue=ipc_queue,
                                               kill_camera_group_flag=kill_camera_group_flag,
                                               )
                camera_loop_thread = threading.Thread(target=camera_group_trigger_loop,
                                                      args=(camera_configs,
                                                            group_orchestrator,
                                                            kill_camera_group_flag))

                frame_wrangler.start()
                camera_manager.start_cameras()
                group_orchestrator.fire_initial_triggers()
                camera_loop_thread.start()

                run_config_queue_listener(camera_manager=camera_manager,
                                          kill_camera_group_flag=kill_camera_group_flag,
                                          config_update_queue=config_update_queue)
        finally:
            kill_camera_group_flag.value = True
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            group_shm.close_and_unlink() if group_shm else None
            logger.debug(f"CameraGroupProcess completed")


def run_config_queue_listener(camera_manager: CameraManager,
                              kill_camera_group_flag: multiprocessing.Value,
                              config_update_queue: multiprocessing.Queue):
    logger.trace(f"Starting config queue listener")
    while not kill_camera_group_flag.value:
        wait_1s()
        if not config_update_queue.empty():
            update_instructions = config_update_queue.get()
            if not isinstance(update_instructions, UpdateInstructions):
                raise ValueError(
                    f"Expected type: `UpdateInstructions`, got type: `{type(update_instructions)}`")
            logger.debug(f"Received update instructions: {update_instructions}")
            if update_instructions.reset_all:
                raise ValueError("Config update requires a reset - this should have happened in the parent process")
            else:
                camera_manager.update_camera_configs(update_instructions)
