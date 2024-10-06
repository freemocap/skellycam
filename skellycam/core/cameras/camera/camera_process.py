import logging
import multiprocessing

import cv2

from skellycam.core.cameras.camera.camera_triggers import CameraTriggers
from skellycam.core.cameras.camera.opencv.apply_config import apply_camera_configuration
from skellycam.core.cameras.camera.config.camera_config import CameraConfig
from skellycam.core.cameras.camera.opencv.get_frame import get_frame
from skellycam.core.cameras.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.shmemory.camera_shared_memory import CameraSharedMemory, SharedMemoryNames
from skellycam.utilities.wait_functions import wait_100us

logger = logging.getLogger(__name__)
AUTO_EXPOSURE_SETTING = 3  # 0.75
MANUAL_EXPOSURE_SETTING = 1  # 0.25


class CameraProcess:
    def __init__(self,
                 config: CameraConfig,
                 shared_memory_names: SharedMemoryNames,
                 shm_valid_flag: multiprocessing.Value,
                 camera_triggers: CameraTriggers,
                 kill_camera_group_flag: multiprocessing.Value,
                 global_kill_event: multiprocessing.Event
                 ):
        self._config = config
        self._config_update_queue = multiprocessing.Queue()  # Queue for updating camera configuration
        self._camera_triggers = camera_triggers

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=f"Camera{self._config.camera_id}",
                                                args=(self._config,
                                                      shared_memory_names,
                                                      shm_valid_flag,
                                                      self._camera_triggers,
                                                      self._config_update_queue,
                                                      kill_camera_group_flag,
                                                      global_kill_event,
                                                      )
                                                )

    @property
    def process(self):
        return self._process

    def start(self):
        self._process.start()

    def close(self):
        logger.info(f"Closing camera {self._config.camera_id}")
        self._camera_triggers.close_self_event.set()
        self._process.join()
        logger.info(f"Camera {self._config.camera_id} closed!")

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def update_config(self, new_config: CameraConfig):
        logger.debug(f"Updating camera {self._config.camera_id} with new config: {new_config}")
        self._config_update_queue.put(new_config)

    @staticmethod
    def _run_process(config: CameraConfig,
                     shared_memory_names: SharedMemoryNames,
                     shm_valid_flag: multiprocessing.Value,
                     camera_triggers: CameraTriggers,
                     config_update_queue: multiprocessing.Queue,
                     kill_camera_group_flag: multiprocessing.Value,
                     global_kill_event: multiprocessing.Event
                     ):
        cv2_video_capture = None
        try:
            camera_shared_memory = CameraSharedMemory.recreate(camera_config=config,
                                                               shared_memory_names=shared_memory_names)

            cv2_video_capture = create_cv2_video_capture(config)
            # cv2_video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING) # TODO - Figure out this manual/auto exposure setting stuff... Linux appears to be always set to AUTO by default and gets weird results when set to MANUAL? And sometimes you have to unplug/replug the camera to fix it?
            logger.debug(f"Camera {config.camera_id} process started")
            apply_camera_configuration(cv2_video_capture, config)
            camera_triggers.set_ready()

            run_trigger_listening_loop(config=config,
                                       cv2_video_capture=cv2_video_capture,
                                       camera_shared_memory=camera_shared_memory,
                                       shm_valid_flag=shm_valid_flag,
                                       camera_triggers=camera_triggers,
                                       config_update_queue=config_update_queue,
                                       kill_camera_group_flag=kill_camera_group_flag,
                                       global_kill_event=global_kill_event,
                                       )
            logger.debug(f"Camera {config.camera_id} process completed")
        finally:
            logger.debug(f"Releasing camera {config.camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
            if cv2_video_capture:
                # cv2_video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_SETTING) # TODO - Figure out this manual/auto exposure setting stuff... See above note
                cv2_video_capture.release()


def run_trigger_listening_loop(
        config: CameraConfig,
        cv2_video_capture: cv2.VideoCapture,
        camera_shared_memory: CameraSharedMemory,
        shm_valid_flag: multiprocessing.Value,
        camera_triggers: CameraTriggers,
        config_update_queue: multiprocessing.Queue,
        kill_camera_group_flag: multiprocessing.Value,
        global_kill_event: multiprocessing.Event
):
    camera_triggers.await_initial_trigger()
    logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
    frame_number = 0
    try:
        # Trigger listening loop
        while not kill_camera_group_flag.value and not camera_triggers.close_self_event.is_set() and not global_kill_event.is_set():

            if config_update_queue.qsize() > 0:
                logger.debug(f"Camera {config.camera_id} received new config update - setting `not ready`")
                camera_triggers.set_not_ready()
                new_config = config_update_queue.get()
                apply_camera_configuration(cv2_video_capture, new_config)
                logger.debug(f"Camera {config.camera_id} updated with new config: {new_config} - setting `ready`")
                camera_triggers.set_ready()

            logger.loop(f"Camera {config.camera_id} ready to get frame# {frame_number}")

            if not shm_valid_flag.value:
                wait_100us()
                continue

            frame_number = get_frame(
                camera_id=config.camera_id,
                cap=cv2_video_capture,
                camera_shared_memory=camera_shared_memory,
                triggers=camera_triggers,
                frame_number=frame_number,
            )
            logger.loop(f"Camera {config.camera_id} got frame# {frame_number} successfully")
    except Exception as e:
        logger.error(f"Camera {config.camera_id} trigger listening loop ended with exception: {e}")
        raise
    finally:
        logger.debug(
            f"Camera {config.camera_id} trigger listening loop ended: close_self_event.is_set()={camera_triggers.close_self_event.is_set()}, "
            f"kill_camera_group_flag={kill_camera_group_flag.value}")
