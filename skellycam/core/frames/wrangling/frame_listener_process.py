import logging
import multiprocessing
import time
from collections import deque
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.camera_group.shmorchestrator.camera_group_shmorchestrator import CameraGroupSharedMemoryOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.timestamps.framerate_tracker import FrameRateTracker
from skellycam.utilities.wait_functions import wait_1us

logger = logging.getLogger(__name__)


class FrameListenerProcess:
    def __init__(
            self,
            dto: CameraGroupDTO,
            frame_escape_pipe: multiprocessing.Pipe,

    ):
        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(dto,
                                                      frame_escape_pipe,
                                                      )
                                                )

    def start(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    @staticmethod
    def _run_process(dto: CameraGroupDTO,
                     frame_escape_pipe: multiprocessing.Pipe,
                     ):
        logger.debug(f"Frame listener process started!")

        try:
            logger.trace(f"Starting FrameListener loop...")
            shmorchestrator = CameraGroupSharedMemoryOrchestrator.recreate(dto=dto.shmorc_dto, read_only=False)
            camera_group_shm = shmorchestrator.shm
            orchestrator = shmorchestrator.orchestrator

            framerate_tracker = FrameRateTracker()
            mf_payload: Optional[MultiFramePayload] = None
            byte_chunklets_to_send = deque()

            while not dto.ipc_flags.kill_camera_group_flag.value and not dto.ipc_flags.global_kill_flag.value:

                if orchestrator.should_pull_multi_frame_from_shm.value:
                    mf_payload: Optional[MultiFramePayload] = camera_group_shm.get_multi_frame_payload(
                        previous_payload=mf_payload)

                    orchestrator.signal_multi_frame_pulled_from_shm()  # NOTE - Reset the flag ASAP after copy to let the frame_loop start the next cycle
                    logger.loop(
                        f"FrameListener - copied multi-frame payload# {mf_payload.multi_frame_number} from shared memory")

                    pulled_from_pipe_timestamp = time.perf_counter_ns()
                    mf_payload.lifespan_timestamps_ns.append({"received_in_frame_router": pulled_from_pipe_timestamp})
                    framerate_tracker.update(pulled_from_pipe_timestamp)
                    # dto.ipc_queue.put(framerate_tracker.current())
                    mf_bytes_list = mf_payload.to_bytes_list()
                    byte_chunklets_to_send.extend(mf_bytes_list)

                elif len(byte_chunklets_to_send) > 0:
                    # Opportunistically let byte chunks escape one-at-a-time, whenever there isn't frame-loop work to do
                    frame_escape_pipe.send_bytes(byte_chunklets_to_send.popleft())
                else:
                    wait_1us()

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
            dto.ipc_flags.kill_camera_group_flag.value = True

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()
