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
            kill_camera_group_flag: multiprocessing.Value,
    ):
        super().__init__()

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(camera_configs,
                                                     group_shm_names,
                                                     group_orchestrator,
                                                     frame_escape_pipe_entrance,
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
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.loop(f"Frame listener process started!")
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        try:

            mf_payload: Optional[MultiFramePayload] = None
            logger.loop(f"Starting FrameListener loop...")

            # Frame listener loop
            byte_payloads_to_send: List[bytes] = []
            while not kill_camera_group_flag.value:
                if group_orchestrator.get_multiframe_from_shm_trigger.is_set():
                    logger.loop(f"FrameListener -  sees new frames available!")

                    mf_payload = camera_group_shm.get_multi_frame_payload_dto(previous_payload_dto=mf_payload)
                    logger.loop(f"FrameListener -  copied multi-frame payload from shared memory")
                    # NOTE - Reset the flag BEFORE we put the payload in the queue to allow new frame loop to begin
                    group_orchestrator.set_multi_frame_pulled_from_shm()

                    logger.loop(f"FrameListener -  cleared escape_multi_frame_trigger")
                    mf_bytes_list = mf_payload.to_bytes_list()
                    byte_payloads_to_send.extend(mf_bytes_list)
                    logger.loop(f"FrameListener -  Sending multi-frame payload `bytes_to_send_list` "
                                f"(size: #frames {len(byte_payloads_to_send)/len(mf_bytes_list)},"
                                f" chunklets: {len(byte_payloads_to_send)}) to FrameRouter")

                else:

                    if len(byte_payloads_to_send) > 0:
                        # Opportunistically send byte chunks one-at-a-time whenever there isn't frame-loop work to do
                        frame_escape_pipe_entrance.send_bytes(byte_payloads_to_send.pop(0))
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
