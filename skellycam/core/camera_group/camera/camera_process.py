import logging
import multiprocessing
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
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import \
    CameraGroupSharedMemoryOrchestrator, CameraGroupSharedMemoryOrchestratorDTO
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)
AUTO_EXPOSURE_SETTING = 3  # 0.75
MANUAL_EXPOSURE_SETTING = 1  # 0.25


@dataclass
class CameraProcess:
    camera_id: CameraId
    process: multiprocessing.Process
    camera_group_dto: CameraGroupDTO
    should_close_self_flag: multiprocessing.Value
    new_config_queue: multiprocessing.Queue

    @classmethod
    def create(cls,
               camera_id: CameraId,
               camera_group_dto: CameraGroupDTO,
               shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO):
        should_close_self_flag = multiprocessing.Value('b', False)
        new_config_queue = multiprocessing.Queue()
        return cls(camera_id=camera_id,
                   camera_group_dto=camera_group_dto,
                   should_close_self_flag=should_close_self_flag,
                   new_config_queue=new_config_queue,
                   process=multiprocessing.Process(target=cls._run_process,
                                                   name=f"Camera{camera_id}",
                                                   args=(camera_id,
                                                         camera_group_dto,
                                                         shmorc_dto,
                                                         new_config_queue,
                                                         should_close_self_flag)
                                                   ),

                   )

    def start(self):
        self.process.start()

    def close(self):
        logger.info(f"Closing camera {self.camera_id}")
        if not self.camera_group_dto.ipc_flags.kill_camera_group_flag.value == True:
            raise ValueError(f"Camera {self.camera_id} was closed before the camera group kill flag was set.")
        self.should_close_self_flag.value = True
        self.process.join()
        logger.info(f"Camera {self.camera_id} closed!")

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def update_config(self, new_config: CameraConfig):
        logger.debug(f"Updating camera {self.camera_id} with new config: {new_config}")
        self.new_config_queue.put(new_config)

    @staticmethod
    def _run_process(camera_id: CameraId,
                     camera_group_dto: CameraGroupDTO,
                     shmorc_dto: CameraGroupSharedMemoryOrchestratorDTO,
                     new_config_queue: multiprocessing.Queue,
                     should_close_self_flag: multiprocessing.Value
                     ):
        config = camera_group_dto.camera_configs[camera_id]
        shmorchestrator = CameraGroupSharedMemoryOrchestrator.recreate(camera_group_dto=camera_group_dto,
                                                                       shmorc_dto=shmorc_dto,
                                                                       read_only=False)
        frame_loop_flags = shmorchestrator.orchestrator.frame_loop_flags[camera_id]
        camera_shm = shmorchestrator.frame_loop_shm.camera_shms[camera_id]

        cv2_video_capture: Optional[cv2.VideoCapture] = None
        try:
            cv2_video_capture = create_cv2_video_capture(config)
            # cv2_video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, MANUAL_EXPOSURE_SETTING) # TODO - Figure out this manual/auto exposure setting stuff... Linux appears to be always set to AUTO by default and gets weird results when set to MANUAL? And sometimes you have to unplug/replug the camera to fix it?
            logger.debug(f"Camera {config.camera_id} process started")
            apply_camera_configuration(cv2_video_capture, config)
            frame_loop_flags.set_camera_ready()

            logger.trace(f"Camera {config.camera_id} trigger listening loop started!")
            frame_number = 0
            # Trigger listening loop
            while not camera_group_dto.ipc_flags.global_kill_flag.value and not camera_group_dto.ipc_flags.kill_camera_group_flag.value and not should_close_self_flag.value:

                if not shmorchestrator.frame_loop_shm.valid:
                    wait_1ms()
                    continue

                if frame_loop_flags.frame_loop_initialization_flag.value:
                    logger.loop(f"Camera {camera_id} received `initialization` signal for frame loop# {frame_number}")
                    frame_loop_flags.frame_loop_initialization_flag.value = False
                    frame_metadata = create_empty_frame_metadata(camera_id=camera_id,
                                                                 config=config,
                                                                 frame_number=frame_number)
                    frame_number = get_frame(
                        camera_id=config.camera_id,
                        cap=cv2_video_capture,
                        frame_metadata=frame_metadata,
                        camera_shared_memory=camera_shm,
                        frame_loop_flags=frame_loop_flags,
                        frame_number=frame_number,
                    )
                    logger.loop(f"Camera {config.camera_id} got frame# {frame_number} successfully")
                else:
                    config = check_for_config_update(config=config,
                                                     cv2_video_capture=cv2_video_capture,
                                                     new_config_queue=new_config_queue,
                                                     frame_loop_flags=frame_loop_flags
                                                     )
                wait_1ms()

            logger.debug(f"Camera {config.camera_id} process completed")
        except Exception as e:
            logger.exception(f"Exception occured when running Camera Process for Camera: {camera_id} - {e}")
            raise
        finally:
            logger.debug(f"Releasing camera {config.camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
            if cv2_video_capture:
                # cv2_video_capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_SETTING) # TODO - Figure out this manual/auto exposure setting stuff... See above note
                cv2_video_capture.release()
            camera_shm.close()

def check_for_config_update(config: CameraConfig,
                            cv2_video_capture: cv2.VideoCapture,
                            new_config_queue: multiprocessing.Queue,
                            frame_loop_flags: CameraFrameLoopFlags) -> CameraConfig:
    if new_config_queue.qsize() > 0:
        logger.debug(f"Camera {config.camera_id} received new config update - setting `not ready`")
        frame_loop_flags.set_camera_not_ready()
        config = new_config_queue.get()
        apply_camera_configuration(cv2_video_capture, config)
        logger.debug(
            f"Camera {config.camera_id} updated with new config: {config} - setting `ready`")
        frame_loop_flags.set_camera_ready()
    return config
