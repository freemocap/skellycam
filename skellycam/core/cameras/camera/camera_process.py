import logging
import multiprocessing

import cv2

from skellycam.core.cameras.camera.camera_triggers import CameraTriggers
from skellycam.core.cameras.camera.config import apply_camera_configuration
from skellycam.core.cameras.camera.config.camera_config import CameraConfig
from skellycam.core.cameras.camera.get_frame import get_frame
from skellycam.core.cameras.camera.opencv import create_cv2_video_capture
from skellycam.core.memory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class CameraProcess:
    def __init__(self,
                 config: CameraConfig,
                 shared_memory_names: SharedMemoryNames,
                 triggers: CameraTriggers,
                 update_queue: multiprocessing.Queue,
                 exit_event: multiprocessing.Event,
                 ):
        self._config = config
        self._update_queue = update_queue
        self._exit_all_event = exit_event  # Shut down all camera processes
        self._close_self_event = multiprocessing.Event()  # Shut down ONLY THIS camera process
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_names,
                                                      triggers,
                                                      self._update_queue,
                                                      self._close_self_event,
                                                      self._exit_all_event,
                                                      )
                                                )



    def start(self):
        self._process.start()

    def close(self):
        logger.debug(f"Closing camera {self._config.camera_id}")
        self._close_self_event.set()
        self._process.join()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_names: SharedMemoryNames,
                     triggers: CameraTriggers,
                     update_queue: multiprocessing.Queue,
                     close_self_event: multiprocessing.Event,
                     exit_event: multiprocessing.Event):
        camera_shared_memory = CameraSharedMemory.recreate(camera_config=config,
                                                           shared_memory_names=shared_memory_names)

        cv2_video_capture = create_cv2_video_capture(config)
        try:
            logger.debug(f"Camera {config.camera_id} process started")
            apply_camera_configuration(cv2_video_capture, config)
            triggers.set_ready()

            run_trigger_listening_loop(config=config,
                                       cv2_video_capture=cv2_video_capture,
                                       camera_shared_memory=camera_shared_memory,
                                       triggers=triggers,
                                       update_queue=update_queue,
                                       close_self_event=close_self_event,
                                       exit_event=exit_event)
            logger.debug(f"Camera {config.camera_id} process completed")
        finally:
            logger.debug(f"Releasing camera {config.camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
            cv2_video_capture.release()


def run_trigger_listening_loop(
        config: CameraConfig,
        cv2_video_capture: cv2.VideoCapture,
        camera_shared_memory: CameraSharedMemory,
        triggers: CameraTriggers,
        update_queue: multiprocessing.Queue,
        close_self_event: multiprocessing.Event,
        exit_event: multiprocessing.Event,
):
    triggers.await_initial_trigger()
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
    frame_number = 0
    try:
        # Trigger listening loop
        while not exit_event.is_set() and not close_self_event.is_set():

            if update_queue.qsize() > 0:
                new_config = update_queue.get()
                apply_camera_configuration(cv2_video_capture, new_config)
                logger.debug(f"Camera {config.camera_id} updated with new config: {new_config}")
            else:
                wait_1ms()

            logger.loop(f"Camera {config.camera_id} ready to get next frame")
            frame_number = get_frame(
                camera_id=config.camera_id,
                cap=cv2_video_capture,
                camera_shared_memory=camera_shared_memory,
                triggers=triggers,
                frame_number=frame_number,
                close_self_event=close_self_event,
            )

    finally:
        logger.debug(f"Camera {config.camera_id} trigger listening loop ended")
