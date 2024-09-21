import logging
import multiprocessing
import time
from typing import Optional, List

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFramePayload
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)

STOP_RECORDING_SIGNAL = "STOP_RECORDING"


class FrameListenerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            group_shm_names: GroupSharedMemoryNames,
            group_orchestrator: CameraGroupOrchestrator,
            frame_escape_pipe_entrance: multiprocessing.Pipe,
            new_multi_frame_payload_in_pipe_flag: multiprocessing.Value,
            kill_camera_group_flag: multiprocessing.Value,
    ):
        super().__init__()

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(camera_configs,
                                                     group_shm_names,
                                                     group_orchestrator,
                                                     frame_escape_pipe_entrance,
                                                        new_multi_frame_payload_in_pipe_flag,
                                                     kill_camera_group_flag,
                                                     )
                                               )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self.process.start()

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     group_shm_names: GroupSharedMemoryNames,
                     group_orchestrator: CameraGroupOrchestrator,
                     frame_escape_pipe_entrance: multiprocessing.Pipe,
                        new_multi_frame_payload_in_pipe_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.success(f"Frame listener process started!")
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        try:

            # group_orchestrator.await_for_cameras_ready() # I don't think i need to wait here?
            mf_payload: Optional[MultiFramePayload] = None
            logger.loop(f"Starting FrameListener loop...")
            # Frame listener loop


            while not kill_camera_group_flag.value:
                if group_orchestrator.new_frames_available:
                    logger.info(f"Frame wrangler sees new frames available!")

                    mf_payload = camera_group_shm.get_multi_frame_payload_dto(previous_payload_dto=mf_payload)
                    logger.info(f"Frame wrangler copied multi-frame payload from shared memory")
                    # NOTE - Reset the flag to allow new frame loop to begin BEFORE we put the payload in the queue
                    group_orchestrator.set_frames_copied()

                    logger.info(
                        f"Sending MultiFrame# {mf_payload.multi_frame_number} to FrameRouter")
                    for dto_item in mf_payload.to_list():
                        frame_escape_pipe_entrance.send_bytes(dto_item)
                        new_multi_frame_payload_in_pipe_flag.value = True
                    logger.info(f"Sent MultiFrame# {mf_payload.multi_frame_number} to FrameRouter successfully")
            else:
                wait_1ms()
        except Exception as e:
            logger.exception(f"Frame listener process error: {e.__class__} - {e}")
            raise
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            camera_group_shm.close()  # close but don't unlink - parent process will unlink
            kill_camera_group_flag.value = True

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def join(self):
        self.process.join()
