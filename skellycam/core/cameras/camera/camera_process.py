import logging
import multiprocessing

import cv2

from skellycam.core.cameras.camera.camera_triggers import CameraTriggers
from skellycam.core.cameras.camera.config.apply_config import apply_camera_configuration
from skellycam.core.cameras.camera.config.camera_config import CameraConfig
from skellycam.core.cameras.camera.get_frame import get_frame
from skellycam.core.cameras.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.shmemory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class CameraProcess:
    def __init__(self,
                 config: CameraConfig,
                 shared_memory_names: SharedMemoryNames,
                 triggers: CameraTriggers,
                 kill_camera_group_flag: multiprocessing.Value,
                 ):
        self._config = config
        self._config_update_queue = multiprocessing.Queue()  # Queue for updating camera configuration
        self._kill_camera_group_flag = kill_camera_group_flag
        self._close_self_flag = multiprocessing.Value("b", False)  # Shut down ONLY THIS camera process
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_names,
                                                      triggers,
                                                      self._config_update_queue,
                                                      self._close_self_flag,
                                                      self._kill_camera_group_flag,
                                                      )
                                                )

    @property
    def process(self):
        return self._process

    def start(self):
        self._process.start()

    def close(self):
        logger.info(f"Closing camera {self._config.camera_id}")
        self._close_self_flag.value = True
        self._process.join()
        self._config_update_queue.close()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def update_config(self, new_config: CameraConfig):
        logger.debug(f"Updating camera {self._config.camera_id} with new config: {new_config}")
        self._config_update_queue.put(new_config)

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_names: SharedMemoryNames,
                     triggers: CameraTriggers,
                     config_update_queue: multiprocessing.Queue,
                     close_self_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
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
                                       config_update_queue=config_update_queue,
                                       close_self_flag=close_self_flag,
                                       kill_camera_group_flag=kill_camera_group_flag, )
            logger.debug(f"Camera {config.camera_id} process completed")
        finally:
            logger.debug(f"Releasing camera {config.camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
            cv2_video_capture.release()


def run_trigger_listening_loop(
        config: CameraConfig,
        cv2_video_capture: cv2.VideoCapture,
        camera_shared_memory: CameraSharedMemory,
        triggers: CameraTriggers,
        config_update_queue: multiprocessing.Queue,
        close_self_flag: multiprocessing.Value,
        kill_camera_group_flag: multiprocessing.Value,
):
    triggers.await_initial_trigger(close_self_flag=close_self_flag)
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
    frame_number = 0
    try:
        # Trigger listening loop
        while not kill_camera_group_flag.value and not close_self_flag.value:

            if config_update_queue.qsize() > 0:
                logger.debug(f"Camera {config.camera_id} received new config update - setting `not ready`")
                triggers.set_not_ready()
                new_config = config_update_queue.get()
                apply_camera_configuration(cv2_video_capture, new_config)
                logger.debug(f"Camera {config.camera_id} updated with new config: {new_config} - setting `ready`")
                triggers.set_ready()

            logger.loop(f"Camera {config.camera_id} ready to get frame# {frame_number}")

            frame_number = get_frame(
                camera_id=config.camera_id,
                cap=cv2_video_capture,
                camera_shared_memory=camera_shared_memory,
                triggers=triggers,
                frame_number=frame_number,
                close_self_flag=close_self_flag,
            )
            logger.loop(f"Camera {config.camera_id} got frame# {frame_number} successfully")
    except Exception as e:
        logger.error(f"Camera {config.camera_id} trigger listening loop ended with exception: {e}")
        raise
    finally:
        logger.debug(f"Camera {config.camera_id} trigger listening loop ended: close_self_flag={close_self_flag.value}, "
                     f"kill_camera_group_flag={kill_camera_group_flag.value}")
