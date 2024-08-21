import logging
import multiprocessing
import threading
from multiprocessing import Process
from typing import Optional

from skellycam.core import CameraId
from skellycam.core.cameras.camera.camera_manager import CameraManager
from skellycam.core.cameras.config.camera_config import CameraConfigs
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
            camera_configs: CameraConfigs,
            frontend_payload_queue: multiprocessing.Queue,
            update_queue: multiprocessing.Queue,
            start_recording_event: multiprocessing.Event,
            exit_event: multiprocessing.Event,
    ):
        self._camera_configs = camera_configs
        self._fe_payload_queue = frontend_payload_queue
        self._update_queue = update_queue
        self._start_recording_event = start_recording_event
        self._exit_event = exit_event

        self._process: Optional[Process] = None

    @property
    def camera_ids(self) -> [CameraId]:
        return [CameraId(camera_id) for camera_id in self._camera_configs.keys()]

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self, number_of_frames: Optional[int] = None):
        logger.debug("Stating CameraTriggerProcess...")
        self._create_process(number_of_frames=number_of_frames)
        self._process.start()

    def close(self):
        logger.debug("Closing CameraTriggerProcess...")
        self._exit_event.set()
        if self._process is not None:
            self._process.join()
        logger.debug("CameraTriggerProcess closed")

    def _create_process(self, number_of_frames: Optional[int] = None):
        self._process = Process(
            name=CameraGroupProcess.__name__,
            target=CameraGroupProcess._run_process,
            args=(self._camera_configs,
                  self._fe_payload_queue,
                  self._update_queue,
                  self._start_recording_event,
                  self._exit_event,
                  number_of_frames
                  )
        )

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     frontend_payload_queue: multiprocessing.Queue,
                     update_queue: multiprocessing.Queue,
                     start_recording_event: multiprocessing.Event,
                     exit_event: multiprocessing.Event,
                     number_of_frames: Optional[int] = None
                     ):
        logger.debug(f"CameraGroupProcess started")
        camera_manager: Optional[CameraManager] = None
        group_shm: Optional[CameraGroupSharedMemory] = None
        frame_wrangler: Optional[FrameWrangler] = None
        try:
            should_continue = True
            while should_continue:

                group_orchestrator = CameraGroupOrchestrator.from_camera_configs(camera_configs=camera_configs,
                                                                                 exit_event=exit_event)

                group_shm = CameraGroupSharedMemory.create(camera_configs=camera_configs)

                frame_wrangler = FrameWrangler(camera_configs=camera_configs,
                                               group_shm_names=group_shm.shared_memory_names,
                                               group_orchestrator=group_orchestrator,
                                               frontend_payload_queue=frontend_payload_queue,
                                               start_recording_event=start_recording_event,
                                               exit_event=exit_event, )
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
