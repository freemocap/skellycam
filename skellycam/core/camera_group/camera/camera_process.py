import logging
import multiprocessing
from dataclasses import dataclass

import cv2

from skellycam.core.camera_group.camera.camera_frame_loop_flags import CameraFrameLoopFlags
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraIdString
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
    camera_id: CameraIdString
    process: multiprocessing.Process
    camera_group_dto: CameraGroupDTO
    new_config_queue: multiprocessing.Queue
    frame_loop_flags: CameraFrameLoopFlags

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               camera_config: CameraConfig,
               camera_group_dto: CameraGroupDTO,
               frame_loop_flags: CameraFrameLoopFlags,
               camera_shared_memory_dto: CameraSharedMemoryDTO):

        new_config_queue = multiprocessing.Queue()
        return cls(camera_id=camera_id,
                   camera_group_dto=camera_group_dto,
                   new_config_queue=new_config_queue,
                   frame_loop_flags=frame_loop_flags,
                   process=multiprocessing.Process(target=cls._run_process,
                                                   name=f"Camera{camera_config.camera_index}-Process",
                                                   daemon=True,
                                                   kwargs=dict(camera_id=camera_id,
                                                               camera_config=camera_config,
                                                               camera_group_dto=camera_group_dto,
                                                                new_config_queue=new_config_queue,
                                                               frame_loop_flags=frame_loop_flags,
                                                               camera_shm_dto=camera_shared_memory_dto)
                                                   ),

                   )

    @staticmethod
    def _run_process(camera_id: CameraIdString,
                     camera_config: CameraConfig,
                     camera_group_dto: CameraGroupDTO,
                     new_config_queue: multiprocessing.Queue,
                     frame_loop_flags: CameraFrameLoopFlags,
                     camera_shm_dto: CameraSharedMemoryDTO,
                     ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=camera_group_dto.ipc.ws_logs_queue)

        def should_continue() -> bool:
            return camera_group_dto.should_continue and not frame_loop_flags.close_self_flag.value

        camera_shm = SingleSlotCameraSharedMemory.recreate(camera_config=camera_config,
                                                           camera_shm_dto=camera_shm_dto,
                                                           read_only=False)
        logger.debug(f"Camera {camera_id} shared memory re-created in CameraProcess for camera {camera_id}")

        cv2_video_capture: cv2.VideoCapture | None = None
        try:
            cv2_video_capture = create_cv2_video_capture(camera_config)

            logger.trace(f"Camera {camera_id} process started")
            camera_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                       config=camera_config,
                                                       initial=True)
            camera_group_dto.ipc.ws_ipc_relay_queue.put({camera_id: camera_config})
            frame_loop_flags.set_camera_ready()
        except Exception as e:
            logger.exception(f"Failed to create `cv2.VideoCapture` for camera {camera_id} - {e}")
            if cv2_video_capture:
                cv2_video_capture.release()
            camera_shm.close()
            frame_loop_flags.close_self_flag.value = True
            return

        try:
            logger.info(f"Camera {camera_config.camera_index} trigger listening loop started!")
            frame_number = 0
            # Trigger listening loop
            while should_continue():
                if frame_loop_flags.frame_loop_initialization_flag.value:
                    logger.loop(f"Camera {camera_id} received `initialization` signal for frame loop# {frame_number}")
                    frame_loop_flags.frame_loop_initialization_flag.value = False
                    frame_metadata = create_empty_frame_metadata(config=camera_config,
                                                                 frame_number=frame_number)
                    frame_number = get_frame(
                        cap=cv2_video_capture,
                        frame_metadata=frame_metadata,
                        camera_shared_memory=camera_shm,
                        frame_loop_flags=frame_loop_flags,
                        frame_number=frame_number,
                    )
                    logger.loop(f"Camera {camera_config.camera_index} got frame# {frame_number-1} successfully")
                else:
                    check_for_config_update(config=camera_config,
                                            cv2_video_capture=cv2_video_capture,
                                            new_config_queue=new_config_queue,
                                            ipc_queue=camera_group_dto.ipc.ws_ipc_relay_queue,
                                            frame_loop_flags=frame_loop_flags,
                                            )

                wait_1ms()

            logger.debug(f"Camera {camera_config.camera_index} process completed")
        except Exception as e:
            logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
            raise
        finally:
            logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
            frame_loop_flags.close_self_flag.value = True
            if cv2_video_capture:
                cv2_video_capture.release()
            camera_shm.close()

    def start(self):
        self.process.start()

    def close(self):
        logger.info(f"Closing camera {self.camera_id}")
        if self.camera_group_dto.should_continue and not self.frame_loop_flags.close_self_flag.value == True:
            raise ValueError(
                f"Camera {self.camera_id} was closed for an unexpected reason! - kill_camera_group_flag: {self.camera_group_dto.ipc.kill_camera_group_flag.value},"
                f" global_kill_flag: {self.camera_group_dto.ipc.global_kill_flag.value}, should_close_self_flag: {self.frame_loop_flags.close_self_flag.value}")
        self.frame_loop_flags.close_self_flag.value = True
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
        logger.debug(f"Camera {config.camera_index} received new config update - setting `not ready`")
        frame_loop_flags.set_camera_not_ready()
        config = new_config_queue.get()
        device_extracted_config = apply_camera_configuration(cv2_video_capture, config)
        logger.debug(
            f"Camera {config.camera_index} updated with new config: {config} - setting `ready`")
        ipc_queue.put(device_extracted_config)
        frame_loop_flags.set_camera_ready()
