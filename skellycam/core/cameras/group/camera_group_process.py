import logging
import multiprocessing
import threading
from multiprocessing import Process
from typing import Optional

from skellycam.core.cameras.camera.camera_manager import CameraManager
from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_loop import camera_group_trigger_loop
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.wrangling.frame_wrangler import FrameWrangler
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_1s, wait_100ms

logger = logging.getLogger(__name__)


class CameraGroupProcess:
    def __init__(
            self,
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
            args=(config_update_queue,
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
    def _run_process(config_update_queue: multiprocessing.Queue,
                     ipc_queue: multiprocessing.Queue,
                     camera_configs: CameraConfigs,
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     global_kill_event: multiprocessing.Event
                     ):
        logger.debug(f"CameraGroupProcess started")
        camera_manager: Optional[CameraManager] = None
        group_shm: Optional[CameraGroupSharedMemory] = None
        frame_wrangler: Optional[FrameWrangler] = None
        camera_loop_thread: Optional[threading.Thread] = None
        try:
            group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs,
                                                                             kill_camera_group_flag=kill_camera_group_flag,
                                                                             global_kill_event=global_kill_event)

            group_shm = CameraGroupSharedMemory.create(camera_configs=camera_configs)
            group_shm_dto = group_shm.to_dto()

            ipc_queue.put(group_shm_dto)

            frame_wrangler = FrameWrangler(group_shm_dto=group_shm_dto,
                                           group_orchestrator=group_orchestrator,
                                           ipc_queue=ipc_queue,
                                           record_frames_flag=record_frames_flag,
                                           kill_camera_group_flag=kill_camera_group_flag,
                                           global_kill_event=global_kill_event,
                                           )
            camera_manager = CameraManager(group_shm_dto=group_shm_dto,
                                           group_orchestrator=group_orchestrator,
                                           kill_camera_group_flag=kill_camera_group_flag,
                                           global_kill_event=global_kill_event,
                                           )
            camera_loop_thread = threading.Thread(target=camera_group_trigger_loop,
                                                  args=(camera_configs,
                                                        group_orchestrator,
                                                        kill_camera_group_flag,
                                                        global_kill_event,
                                                        ))

            frame_wrangler.start()
            camera_loop_thread.start()
            camera_manager.start_cameras()

            run_config_queue_listener(camera_manager=camera_manager,
                                      camera_group_orchestrator=group_orchestrator,
                                      kill_camera_group_flag=kill_camera_group_flag,
                                      global_kill_event=global_kill_event,
                                      config_update_queue=config_update_queue)
        except Exception as e:
            logger.error(f"CameraGroupProcess error: {e}")
            logger.exception(e)
            raise
        finally:
            kill_camera_group_flag.value = True
            frame_wrangler.close() if frame_wrangler else None
            camera_manager.close() if camera_manager else None
            camera_loop_thread.join() if camera_loop_thread else None
            group_shm.close_and_unlink() if group_shm else None
            logger.debug(f"CameraGroupProcess completed")


def run_config_queue_listener(camera_manager: CameraManager,
                              camera_group_orchestrator: CameraGroupOrchestrator,
                              kill_camera_group_flag: multiprocessing.Value,
                              global_kill_event: multiprocessing.Event,
                              config_update_queue: multiprocessing.Queue):
    logger.trace(f"Starting config queue listener")
    while not kill_camera_group_flag.value and not global_kill_event.is_set():
        wait_1s()
        if config_update_queue.qsize() > 0:
            logger.trace(f"Config update queue has {config_update_queue.qsize()} items, pausing frame loop to update configs")
            camera_group_orchestrator.pause_loop()
            while not camera_group_orchestrator.frame_loop_paused:  # Wait for the frame loop to pause before updating configs
                wait_100ms()

            update_instructions = config_update_queue.get()

            camera_manager.update_camera_configs(update_instructions)
            camera_group_orchestrator.unpause_loop()
