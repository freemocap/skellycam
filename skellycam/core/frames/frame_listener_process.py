import logging
import multiprocessing
import pickle
import time
from typing import Optional

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.cameras.group.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload
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
            video_recorder_queue: multiprocessing.Queue,
            frontend_pipe: multiprocessing.Pipe,
            record_frames_flag: multiprocessing.Value,
            kill_camera_group_flag: multiprocessing.Value,
    ):
        super().__init__()

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(camera_configs,
                                                     group_shm_names,
                                                     group_orchestrator,
                                                     video_recorder_queue,
                                                     frontend_pipe,
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
                     video_recorder_queue: multiprocessing.Queue,
                     frontend_pipe: multiprocessing.Pipe,
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value, ):
        logger.trace(f"Frame listener process started!")
        camera_group_shm = CameraGroupSharedMemory.recreate(
            camera_configs=camera_configs,
            group_shm_names=group_shm_names,
        )
        try:

            group_orchestrator.await_for_cameras_ready()
            mf_payload: Optional[MultiFramePayload] = None
            logger.loop(f"Starting FrameListener loop...")
            # Frame listener loop
            is_recording = False
            while not kill_camera_group_flag.value:
                if group_orchestrator.new_frames_available:
                    logger.loop(f"Frame wrangler sees new frames available!")
                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload)
                    # NOTE - Reset the flag to allow new frame loop to begin BEFORE we put the payload in the queue
                    group_orchestrator.set_frames_copied()

                    if record_frames_flag.value:
                        is_recording = True
                        mf_payload.lifespan_timestamps_ns.append(
                            {"before_put_in_video_recording_queue": time.perf_counter_ns()})
                        video_recorder_queue.put(mf_payload)
                    elif not record_frames_flag.value and is_recording:  # we just stopped recording, need to finish up the video
                        is_recording = False
                        logger.debug(f"FrameListener - Sending STOP signal to video recorder")
                        video_recorder_queue.put(STOP_RECORDING_SIGNAL)
                    # Pickle and send_bytes, to avoid paying the pickle cost twice when relaying through websocket
                    frontend_bytes = pickle.dumps(FrontendFramePayload.from_multi_frame_payload(mf_payload))
                    frontend_pipe.send_bytes(frontend_bytes)
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
