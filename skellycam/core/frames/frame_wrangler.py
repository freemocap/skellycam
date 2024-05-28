import logging
import multiprocessing
from typing import Optional, Dict

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.cameras.trigger_camera.multi_camera_triggers import MultiCameraTriggerOrchestrator
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import SharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            shared_memory_names: Dict[CameraId, SharedMemoryNames],
            multicam_triggers: MultiCameraTriggerOrchestrator,
            exit_event: multiprocessing.Event,
    ):
        super().__init__()
        self._payloads_received: multiprocessing.Value = multiprocessing.Value("i", 0)
        self._exit_event = exit_event

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(camera_configs,
                                                      shared_memory_names,
                                                      multicam_triggers,
                                                      self._payloads_received,
                                                      exit_event,
                                                      )
                                                )

    @property
    def payloads_received(self) -> int:
        return self._payloads_received.value

    def start_process(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     shared_memory_names: Dict[CameraId, SharedMemoryNames],
                     multicam_triggers: MultiCameraTriggerOrchestrator,
                     payloads_received: multiprocessing.Value,
                     exit_event: multiprocessing.Event):
        camera_shm_manager = CameraSharedMemoryManager.recreate(
            camera_configs=camera_configs,
            shared_memory_names=shared_memory_names,
        )
        logger.trace(f"Frame listener process started")
        multicam_triggers.wait_for_cameras_ready()
        payload: Optional[MultiFramePayload] = None
        try:
            while not exit_event.is_set():
                if multicam_triggers.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")
                    payload = camera_shm_manager.get_multi_frame_payload(previous_payload=payload)
                    multicam_triggers.set_frames_copied()
                    payloads_received.value += 1
                else:
                    wait_1ms()

        except Exception as e:
            logger.error(f"Error in listen_for_frames: {type(e).__name__} - {e}")
            logger.exception(e)
        logger.trace(f"Stopped listening for multi-frames")

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()


class FrameWrangler:
    def __init__(self, exit_event: multiprocessing.Event):
        super().__init__()
        self._exit_event = exit_event

        self._camera_configs: Optional[CameraConfigs] = None
        self._multicam_triggers: Optional[MultiCameraTriggerOrchestrator] = None
        self._shared_memory_names: Optional[Dict[CameraId, SharedMemoryNames]] = None

        self._listener_process: Optional[FrameListenerProcess] = None

    @property
    def payloads_received(self) -> Optional[int]:
        if self._listener_process is None:
            return None
        return self._listener_process.payloads_received

    def set_camera_info(
            self,
            camera_configs: CameraConfigs,
            shared_memory_names: Dict[CameraId, SharedMemoryNames],
            multicam_triggers: MultiCameraTriggerOrchestrator,
    ):
        logger.debug(f"Setting camera configs to {camera_configs}")

        self._camera_configs = camera_configs
        self._multicam_triggers = multicam_triggers
        self._shared_memory_names = shared_memory_names

    def start_frame_listener(self):
        logger.debug(f"Starting frame listener process...")

        self._listener_process = FrameListenerProcess(
            camera_configs=self._camera_configs,
            multicam_triggers=self._multicam_triggers,
            shared_memory_names=self._shared_memory_names,
            exit_event=self._exit_event,
        )
        self._listener_process.start_process()

    def is_alive(self) -> bool:
        return self._listener_process.is_alive()

    def join(self):
        self._listener_process.join()

    def close(self):
        logger.debug(f"Closing frame wrangler...")
        self._exit_event.set()
        if self._listener_process is not None:
            self._listener_process.join()
