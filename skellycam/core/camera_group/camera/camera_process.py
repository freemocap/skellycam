import logging
import multiprocessing
import time
from dataclasses import dataclass
from typing import Optional

import cv2

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera.opencv.apply_config import apply_camera_configuration
from skellycam.core.camera_group.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera_group.camera.opencv.get_frame import get_frame
from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.shared_memory.single_slot_camera_shared_memory import \
    SingleSlotCameraSharedMemory, CameraSharedMemoryDTO
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class CameraProcess:
    camera_id: CameraId
    process: multiprocessing.Process
    camera_group_dto: CameraGroupDTO
    should_close_self_flag: multiprocessing.Value
    new_config_queue: multiprocessing.Queue

    @classmethod
    def create(cls,
               camera_config: CameraConfig,
               camera_group_dto: CameraGroupDTO,
               frame_loop_flags: CameraFrameLoopFlags,
               camera_shared_memory_dto: CameraSharedMemoryDTO):

        should_close_self_flag = multiprocessing.Value('b', False)
        new_config_queue = multiprocessing.Queue()
        return cls(camera_id=camera_config.camera_id,
                   camera_group_dto=camera_group_dto,
                   should_close_self_flag=should_close_self_flag,
                   new_config_queue=new_config_queue,
                   process=multiprocessing.Process(target=cls._run_process,
                                                   name=f"Camera{camera_config.camera_id}-Process",
                                                   daemon=True,
                                                   kwargs=dict(camera_config=camera_config,
                                                               camera_group_dto=camera_group_dto,
                                                               frame_loop_flags=frame_loop_flags,
                                                               camera_shm_dto=camera_shared_memory_dto,
                                                               new_config_queue=new_config_queue,
                                                               ipc_queue=camera_group_dto.ipc_queue,
                                                               should_close_self_flag=should_close_self_flag)
                                                   ),

                   )

    @staticmethod
    def _run_process(camera_config: CameraConfig,
                     camera_group_dto: CameraGroupDTO,
                     frame_loop_flags: CameraFrameLoopFlags,
                     camera_shm_dto: CameraSharedMemoryDTO,
                     new_config_queue: multiprocessing.Queue,
                     ipc_queue: multiprocessing.Queue,
                     should_close_self_flag: multiprocessing.Value
                     ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        camera_id = camera_config.camera_id
        configure_logging(LOG_LEVEL, ws_queue=camera_group_dto.logs_queue)

        def heartbeat_thread_function():
            heartbeat_counter = 0
            while camera_group_dto.should_continue and not should_close_self_flag.value:
                heartbeat_counter += 1
                if heartbeat_counter % 10 == 0:
                    logger.trace(f"Camera#{camera_id} Process heartbeat says 'beep'")
                time.sleep(1)

        camera_shm = SingleSlotCameraSharedMemory.recreate(camera_config=camera_config,
                                                           camera_shm_dto=camera_shm_dto,
                                                           read_only=False)
        logger.debug(f"Camera {camera_id} shared memory re-created in CameraProcess for camera {camera_id}")
        cv2_video_capture: Optional[cv2.VideoCapture] = None
        try:
            cv2_video_capture = create_cv2_video_capture(camera_config)

            logger.trace(f"Camera {camera_config.camera_id} process started")
            camera_config = apply_camera_configuration(cv2_video_capture, camera_config, initial=True)
            ipc_queue.put(camera_config)
            frame_loop_flags.set_camera_ready()

            logger.info(f"Camera {camera_config.camera_id} trigger listening loop started!")
            frame_number = 0
            # Trigger listening loop
            while camera_group_dto.should_continue and not should_close_self_flag.value:
                if frame_loop_flags.frame_loop_initialization_flag.value:
                    logger.loop(f"Camera {camera_id} received `initialization` signal for frame loop# {frame_number}")
                    frame_loop_flags.frame_loop_initialization_flag.value = False
                    frame_metadata = create_empty_frame_metadata(camera_id=camera_id,
                                                                 config=camera_config,
                                                                 frame_number=frame_number)
                    frame_number = get_frame(
                        camera_id=camera_config.camera_id,
                        cap=cv2_video_capture,
                        frame_metadata=frame_metadata,
                        camera_shared_memory=camera_shm,
                        frame_loop_flags=frame_loop_flags,
                        frame_number=frame_number,
                    )
                    logger.loop(f"Camera {camera_config.camera_id} got frame# {frame_number} successfully")
                else:
                    check_for_config_update(config=camera_config,
                                            cv2_video_capture=cv2_video_capture,
                                            new_config_queue=new_config_queue,
                                            ipc_queue=ipc_queue,
                                            frame_loop_flags=frame_loop_flags,
                                            )

                wait_1ms()

            logger.debug(f"Camera {camera_config.camera_id} process completed")
        except Exception as e:
            logger.exception(f"Exception occured when running Camera Process for Camera: {camera_id} - {e}")
            raise
        finally:
            logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
            if cv2_video_capture:
                cv2_video_capture.release()
            camera_shm.close()

    def start(self):
        self.process.start()

    def close(self):
        logger.info(f"Closing camera {self.camera_id}")
        if self.camera_group_dto.should_continue and not self.should_close_self_flag.value == True:
            raise ValueError(
                f"Camera {self.camera_id} was closed for an unexpected reason! - kill_camera_group_flag: {self.camera_group_dto.ipc_flags.kill_camera_group_flag.value},"
                f" global_kill_flag: {self.camera_group_dto.ipc_flags.global_kill_flag.value}, should_close_self_flag: {self.should_close_self_flag.value}")
        self.should_close_self_flag.value = True
        self.process.join()
        logger.info(f"Camera {self.camera_id} closed!")

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def update_config(self, new_config: CameraConfig):
        logger.debug(f"Updating camera {self.camera_id} with new config: {new_config}")
        self.new_config_queue.put(new_config)


def check_for_config_update(config: CameraConfig,
                            cv2_video_capture: cv2.VideoCapture,
                            new_config_queue: multiprocessing.Queue,
                            ipc_queue: multiprocessing.Queue,
                            frame_loop_flags: CameraFrameLoopFlags,
                            ):
    if not new_config_queue.empty():
        logger.debug(f"Camera {config.camera_id} received new config update - setting `not ready`")
        frame_loop_flags.set_camera_not_ready()
        config = new_config_queue.get()
        device_extracted_config = apply_camera_configuration(cv2_video_capture, config)
        logger.debug(
            f"Camera {config.camera_id} updated with new config: {config} - setting `ready`")
        ipc_queue.put(device_extracted_config)
        frame_loop_flags.set_camera_ready()
