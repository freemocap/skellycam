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
            update_queue: multiprocessing.Queue,
    ):
        self._fe_payload_pipe = frontend_pipe
        self._update_queue = update_queue
        self._backend_state: AppState = get_app_state()
        self._process = Process(
            name=CameraGroupProcess.__name__,
            target=CameraGroupProcess._run_process,
            args=(self._backend_state.camera_configs,
                  self._fe_payload_pipe,
                  self._update_queue,
                  self._backend_state.record_frames_flag,
                  self._backend_state.kill_camera_group_flag
                  )
        )

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    async def start(self):
        logger.debug("Starting `CameraGroupProcess`...")
        self._process.start()
        await self._backend_state.add_process(self._process)

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     frontend_pipe: multiprocessing.Pipe,
                     update_queue: multiprocessing.Queue,
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.debug(f"CameraGroupProcess started")
        camera_manager: Optional[CameraManager] = None
        group_shm: Optional[CameraGroupSharedMemory] = None
        frame_wrangler: Optional[FrameWrangler] = None
        try:
            should_continue = True
            while should_continue and not kill_camera_group_flag.value:

                group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs,
                                                                                 kill_camera_group_flag=kill_camera_group_flag)

                group_shm = CameraGroupSharedMemory.create(camera_configs=camera_configs)

                frame_wrangler = FrameWrangler(camera_configs=camera_configs,
                                               group_shm_names=group_shm.shared_memory_names,
                                               group_orchestrator=group_orchestrator,
                                               frontend_pipe=frontend_pipe,
                                               record_frames_flag=record_frames_flag,
                                               kill_camera_group_flag=kill_camera_group_flag)
                camera_manager = CameraManager(camera_configs=camera_configs,
                                               shared_memory_names=group_shm.shared_memory_names,
                                               group_orchestrator=group_orchestrator,
                                               exit_event=exit_event,
                                               )
                camera_loop_thread = threading.Thread(target=camera_group_trigger_loop,
                                                      args=(camera_configs,
                                                            group_orchestrator,
                                                            exit_event))

                frame_wrangler.start()
                camera_manager.start_cameras()
                group_orchestrator.fire_initial_triggers()
                camera_loop_thread.start()

                reset_all = False
                while not exit_event.is_set():
                    if reset_all:
                        break
                    wait_1s()
                    if not update_queue.empty():
                        update_instructions = update_queue.get()
                        if not isinstance(update_instructions, UpdateInstructions):
                            raise ValueError(
                                f"Expected type: `UpdateInstructions`, got type: `{type(update_instructions)}`")
                        logger.debug(f"Received update instructions: {update_instructions}")
                        if update_instructions.reset_all:
                            camera_configs = update_instructions.camera_configs
                            reset_all = True
                        else:
                            camera_manager.update_cameras(update_instructions)
        finally:
            exit_event.set()
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            group_shm.close_and_unlink() if group_shm else None
            logger.debug(f"CameraGroupProcess completed")
