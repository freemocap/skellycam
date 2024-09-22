import logging
import multiprocessing
import time
from typing import Optional, List

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory import GroupSharedMemoryNames
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemory, CameraGroupSharedMemoryDTO
from skellycam.core.timestamps.frame_rate_tracker import FrameRateTracker
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            group_shm_dto: CameraGroupSharedMemoryDTO,
            group_orchestrator: CameraGroupOrchestrator,
            frame_escape_pipe_entrance: multiprocessing.Pipe,
            ipc_queue: multiprocessing.Queue,
            kill_camera_group_flag: multiprocessing.Value,
    ):
        super().__init__()

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(group_shm_dto,
                                                     group_orchestrator,
                                                     frame_escape_pipe_entrance,
                                                     ipc_queue,
                                                     kill_camera_group_flag,
                                                     )
                                               )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self.process.start()

    @staticmethod
    def _run_process(group_shm_dto: CameraGroupSharedMemoryDTO,
                     group_orchestrator: CameraGroupOrchestrator,
                     frame_escape_pipe_entrance: multiprocessing.Pipe,
                     ipc_queue: multiprocessing.Queue,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.loop(f"Frame listener process started!")
        camera_group_shm = CameraGroupSharedMemory.recreate(dto=group_shm_dto)
        frame_rate_tracker = FrameRateTracker()


        try:
            mf_payload: Optional[MultiFramePayload] = None
            logger.loop(f"Starting FrameListener loop...")

            # Frame listener loop
            byte_payloads_to_send: List[bytes] = []
            while not kill_camera_group_flag.value:
                if group_orchestrator.get_multiframe_from_shm_trigger.is_set():
                    logger.loop(f"FrameListener -  sees new frames available!")

                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload,
                                                                          read_only=False)
                    logger.loop(f"FrameListener -  copied multi-frame payload from shared memory")
                    # NOTE - Reset the flag to let the frame_loop start the next cycle
                    group_orchestrator.set_multi_frame_pulled_from_shm()
                    frame_rate_tracker.update(time.perf_counter_ns())

                    ipc_queue.put(frame_rate_tracker.current())

                    logger.loop(f"FrameListener -  cleared escape_multi_frame_trigger")
                    mf_bytes_list = mf_payload.to_bytes_list()
                    byte_payloads_to_send.extend(mf_bytes_list)
                    logger.loop(f"FrameListener -  Sending multi-frame payload `bytes_to_send_list` "
                                f"(size: #frames {len(byte_payloads_to_send) / len(mf_bytes_list)},"
                                f" chunklets: {len(byte_payloads_to_send)}) to FrameRouter")

                else:
                    if len(byte_payloads_to_send) > 0:
                        # Opportunistically let byte chunks escape one-at-a-time,
                        # whenever there isn't frame-loop work to do
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
