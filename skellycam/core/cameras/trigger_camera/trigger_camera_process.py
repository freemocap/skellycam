import logging
import multiprocessing

from skellycam.core.cameras.config.apply_config import apply_camera_configuration
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.cameras.opencv.create_cv2_video_capture import create_cv2_capture
from skellycam.core.cameras.trigger_camera.camera_triggers import SingleCameraTriggers
from skellycam.core.cameras.trigger_camera.trigger_listening_loop import run_trigger_listening_loop
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames

logger = logging.getLogger(__name__)


class TriggerCameraProcess:
    def __init__(self,
                 config: CameraConfig,
                 shared_memory_names: SharedMemoryNames,
                 triggers: SingleCameraTriggers,
                 exit_event: multiprocessing.Event,
                 ):
        self._config = config

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_names,
                                                      triggers,
                                                      exit_event
                                                      )
                                                )

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_names: SharedMemoryNames,
                     triggers: SingleCameraTriggers,
                     exit_event: multiprocessing.Event):
        logger.debug(f"Camera {config.camera_id} process started")
        camera_shared_memory = CameraSharedMemory.recreate(camera_config=config,
                                                           shared_memory_names=shared_memory_names)

        cv2_video_capture = create_cv2_capture(config)

        apply_camera_configuration(cv2_video_capture, config)
        triggers.set_ready()
        run_trigger_listening_loop(config=config,
                                   cv2_video_capture=cv2_video_capture,
                                   camera_shared_memory=camera_shared_memory,
                                   triggers=triggers,
                                   exit_event=exit_event)
        cv2_video_capture.release()
        logger.debug(f"Camera {config.camera_id} process completed")

    def start(self):
        self._process.start()
