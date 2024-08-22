import logging
import multiprocessing
import pickle
import time
from typing import Optional, Union

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.frame_listener_process import STOP_RECORDING_SIGNAL
from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload
from skellycam.core.videos.video_recorder_manager import VideoRecorderManager
from skellycam.system.default_paths import create_recording_folder
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)

class FrameSaverProcess:
    def __init__(self,
                 video_recorder_queue: multiprocessing.Queue,
                 frontend_pipe: multiprocessing.Pipe,
                 camera_configs: CameraConfigs,
                 kill_camera_group_flag: multiprocessing.Value, ):

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(video_recorder_queue,
                                                     frontend_pipe,
                                                     camera_configs,
                                                     kill_camera_group_flag))

    def start(self):
        logger.trace(f"Starting frame listener process")
        self.process.start()

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def join(self):
        self.process.join()

    @staticmethod
    def _run_process(video_recorder_queue: multiprocessing.Queue,
                     frontend_pipe: multiprocessing.Pipe,
                     camera_configs: CameraConfigs,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        logger.trace(f"Frame exporter process started!")
        multi_frame_saver: Optional[VideoRecorderManager] = None

        try:
            while not kill_camera_group_flag.value:
                if not video_recorder_queue.empty():
                    payload: Union[MultiFramePayload, str] = video_recorder_queue.get()

                    if isinstance(payload, str) and payload == STOP_RECORDING_SIGNAL:
                        logger.trace(f"Received STOP signal - closing video recorder")
                        if multi_frame_saver:
                            logger.debug(
                                f"FrameExporter - Closing FrameSaver for recording {multi_frame_saver.recording_name}")
                            multi_frame_saver.close()
                            multi_frame_saver = None
                    elif isinstance(payload, MultiFramePayload):
                        logger.loop(f"FrameExporter - Received multi-frame payload: {payload}")

                        if not multi_frame_saver:  # create new multi_frame_saver on first multi-frame payload
                            multi_frame_saver = VideoRecorderManager.create(mf_payload=payload,
                                                                            camera_configs=camera_configs,
                                                                            recording_folder=create_recording_folder(
                                                                                string_tag=None))
                            logger.success(
                                f"FrameExporter - Created FrameSaver for recording {multi_frame_saver.recording_name}")
                            # send  as bytes so it can use same ws/ relay as the frontend_payload's
                            frontend_pipe.send_bytes(pickle.dumps(multi_frame_saver.recording_info))
                        payload.lifespan_timestamps_ns.append({"pulled_from_mf_queue": time.perf_counter_ns()})

                        multi_frame_saver.add_multi_frame(payload)
                else:
                    wait_1ms()
        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
            logger.traceback(e)
            raise e
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if multi_frame_saver:
                multi_frame_saver.close()
            kill_camera_group_flag.value = True
