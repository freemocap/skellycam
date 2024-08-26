import logging
import multiprocessing
import time
from typing import Optional, List

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
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
            record_frames_flag: multiprocessing.Value,
            kill_camera_group_flag: multiprocessing.Value,
    ):
        super().__init__()

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(camera_configs,
                                                     group_shm_names,
                                                     group_orchestrator,
                                                     frame_escape_pipe_entrance,
                                                     record_frames_flag,
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
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.trace(f"Frame listener process started!")
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        try:

            # group_orchestrator.await_for_cameras_ready() # I don't think i need to wait here?
            mf_payload: Optional[MultiFramePayload] = None
            logger.loop(f"Starting FrameListener loop...")
            # Frame listener loop
            escape_buffer: List[MultiFramePayload] = []
            recording_in_progress: bool = False
            while not kill_camera_group_flag.value:
                if record_frames_flag.value:
                    recording_in_progress = True
                if group_orchestrator.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")

                    # TODO - RECEIVE AS BYTES and send to `frame_router` w/ `pipe.send_bytes()` and construct mf_payload after escaping frame loop
                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload)

                    # NOTE - Reset the flag to allow new frame loop to begin BEFORE we put the payload in the queue
                    group_orchestrator.set_frames_copied()
                    mf_payload.lifespan_timestamps_ns.append(
                        {"before_put_in_escape_buffer": time.perf_counter_ns()})

                    escape_buffer.append(mf_payload)

                    if recording_in_progress and not record_frames_flag.value:
                        # We just ended a recording - this is the only time we are allowed to freeze the frame-loop so we can drain the buffer and make sure all frames make it to disk
                        while len(escape_buffer) > 0:
                            frame_escape_pipe_entrance.send(escape_buffer.pop(0))

                    if not group_orchestrator.new_frames_available:
                        # Prioritize frame-loop sanctity - hold frame in buffer if new frames available
                        # TODO - WARNING - Could result in frontend lag (or even no frames making it to frontend in extreme cases). Prob set a min fps of like 5-10 to the tool usable
                        # TODO - send frames one at a time to minimize blocking (and using `send_bytes`, per above)
                        frame_escape_pipe_entrance.send(escape_buffer.pop(0)) if len(escape_buffer) > 0 else None
            else:
                wait_1ms()
        except Exception as e:
            logger.exception(f"Frame listener process error: {e.__class__} - {e}")
            raise e
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            camera_group_shm.close()  # close but don't unlink - parent process will unlink
            kill_camera_group_flag.value = True

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def join(self):
        self.process.join()
