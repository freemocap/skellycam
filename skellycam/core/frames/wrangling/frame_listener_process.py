import logging
import multiprocessing
import time
from collections import deque
from typing import Optional

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO, CameraGroupSharedMemory
from skellycam.core.timestamps.frame_rate_tracker import FrameRateTracker
from skellycam.utilities.wait_functions import wait_100us

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            group_shm_dto: CameraGroupSharedMemoryDTO,
            group_orchestrator: CameraGroupOrchestrator,
            frame_escape_pipe: multiprocessing.Pipe,
            ipc_queue: multiprocessing.Queue,
            kill_camera_group_flag: multiprocessing.Value,
            global_kill_event: multiprocessing.Event,
    ):
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(group_shm_dto,
                                                     group_orchestrator,
                                                     frame_escape_pipe,
                                                     ipc_queue,
                                                     kill_camera_group_flag,
                                                     global_kill_event,
                                                     )
                                                )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(group_shm_dto: CameraGroupSharedMemoryDTO,
                     group_orchestrator: CameraGroupOrchestrator,
                     frame_escape_pipe: multiprocessing.Pipe,
                     ipc_queue: multiprocessing.Queue,
                     kill_camera_group_flag: multiprocessing.Value,
                     global_kill_event: multiprocessing.Event
                     ):
        logger.debug(f"Frame listener process started!")

        try:
            logger.trace(f"Starting FrameListener loop...")
            camera_group_shm = CameraGroupSharedMemory.recreate(dto=group_shm_dto)
            frame_rate_tracker = FrameRateTracker()
            mf_payload: Optional[MultiFramePayload] = None
            byte_chunklets_to_send = deque()
            while not kill_camera_group_flag.value and not global_kill_event.is_set():
                if group_orchestrator.new_multi_frame_put_in_shm.is_set():
                    mf_payload: Optional[MultiFramePayload] = camera_group_shm.get_multi_frame_payload(
                        previous_payload=mf_payload,
                        read_only=False)  # will increment mf_number so the FrontendFrameRelay will notice the new data
                    if mf_payload is None:
                        logger.error(f"FrameListener -  failed to get multi-frame payload from shared memory")
                        continue
                    group_orchestrator.set_multi_frame_pulled_from_shm()  # NOTE - Reset the flag ASAP after copy to let the frame_loop start the next cycle
                    logger.loop(
                        f"FrameListener -  copied multi-frame payload# {mf_payload.multi_frame_number} from shared memory")

                    pulled_from_pipe_timestamp = time.perf_counter_ns()
                    mf_payload.lifespan_timestamps_ns.append({"received_in_frame_router": pulled_from_pipe_timestamp})
                    frame_rate_tracker.update(pulled_from_pipe_timestamp)
                    ipc_queue.put(frame_rate_tracker.current())
                    mf_bytes_list = mf_payload.to_bytes_list()
                    byte_chunklets_to_send.extend(mf_bytes_list)

                elif len(byte_chunklets_to_send) > 0 and not group_orchestrator.new_multi_frame_put_in_shm.is_set():
                    # Opportunistically let byte chunks escape one-at-a-time, whenever there isn't frame-loop work to do
                    frame_escape_pipe.send_bytes(byte_chunklets_to_send.popleft())

                else:
                    wait_100us()

        except Exception as e:
            logger.exception(f"Frame listener process error: {e.__class__} - {e}")
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame exporter process error: {e} - Broken pipe error, problem in FrameRouterProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            logger.info(f"Frame exporter process received KeyboardInterrupt, shutting down gracefully...")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if not kill_camera_group_flag.value:
                kill_camera_group_flag.value = True
                raise RuntimeError("FrameListenerProcess stopped without kill flag set!")

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()

