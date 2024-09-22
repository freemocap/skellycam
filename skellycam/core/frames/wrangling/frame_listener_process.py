import logging
import multiprocessing
from typing import Optional

from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO
from skellycam.utilities.wait_functions import wait_1us

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            group_orchestrator: CameraGroupOrchestrator,
            new_mf_ready_flag: multiprocessing.Value,
            kill_camera_group_flag: multiprocessing.Value,
    ):
        super().__init__()

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=( group_orchestrator,
                                                     new_mf_ready_flag,
                                                     kill_camera_group_flag,
                                                     )
                                               )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self.process.start()

    @staticmethod
    def _run_process(group_orchestrator: CameraGroupOrchestrator,
                     new_mf_ready_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.debug(f"Frame listener process started!")

        try:
            logger.trace(f"Starting FrameListener loop...")

            while not kill_camera_group_flag.value:
                if group_orchestrator.new_multi_frame_put_in_shm.is_set():
                    new_mf_ready_flag.value = True
                    while new_mf_ready_flag.value:
                        wait_1us()
                    group_orchestrator.set_multi_frame_pulled_from_shm()
                else:
                    wait_1us()




        except Exception as e:
            logger.exception(f"Frame listener process error: {e.__class__} - {e}")
            raise
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            kill_camera_group_flag.value = True

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def join(self):
        self.process.join()

#     mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload,
#                                                           read_only=False)
#     logger.loop(f"FrameListener -  copied multi-frame payload from shared memory")
#     # NOTE - Reset the flag to let the frame_loop start the next cycle
#     group_orchestrator.set_multi_frame_pulled_from_shm()
#     frame_rate_tracker.update(time.perf_counter_ns())
#
#     ipc_queue.put(frame_rate_tracker.current())
#
#     logger.loop(f"FrameListener -  cleared escape_multi_frame_trigger")
#     mf_bytes_list = mf_payload.to_bytes_list()
#     byte_payloads_to_send.extend(mf_bytes_list)
#     logger.loop(f"FrameListener -  Sending multi-frame payload `bytes_to_send_list` "
#                 f"(size: #frames {len(byte_payloads_to_send) / len(mf_bytes_list)},"
#                 f" chunklets: {len(byte_payloads_to_send)}) to FrameRouter")
#
# else:
# if len(byte_payloads_to_send) > 0:
#     # Opportunistically let byte chunks escape one-at-a-time,
#     # whenever there isn't frame-loop work to do
#     frame_escape_pipe_entrance.send_bytes(byte_payloads_to_send.pop(0))
