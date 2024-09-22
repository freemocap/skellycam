import logging
import multiprocessing
import time
from typing import Optional, Dict

from skellycam.core.cameras.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.timestamps.frame_rate_tracker import FrameRateTracker, CurrentFrameRate
from skellycam.core.videos.video_recorder_manager import VideoRecorderManager
from skellycam.system.default_paths import create_recording_folder
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class FrameRouterProcess:
    def __init__(self,
                 camera_configs: CameraConfigs,
                 frame_escape_pipe_exit: multiprocessing.Pipe,
                 frontend_relay_pipe: multiprocessing.Pipe,
                 record_frames_flag: multiprocessing.Value,
                 kill_camera_group_flag: multiprocessing.Value, ):

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(camera_configs,
                                                     frame_escape_pipe_exit,
                                                     frontend_relay_pipe,
                                                     record_frames_flag,
                                                     kill_camera_group_flag))

    def start(self):
        logger.trace(f"Starting frame listener process")
        self.process.start()

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def join(self):
        self.process.join()

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     frame_escape_pipe_exit: multiprocessing.Pipe,
                     frontend_relay_pipe: multiprocessing.Pipe,
                     record_frames_flag: multiprocessing.Value,
                     kill_camera_group_flag: multiprocessing.Value,
                     ):
        """
        This process is not coupled to the frame loop, and the `escape pipe` is elastic, so blocking is not as big a sin here.
        Frame chunks will be sent through the `frame_escape_pipe_exit` and will be gathered, reconstructed into a framepayload, and handled here.
        Mostly need to ensure that the all frames are saved (Priority #1) and that the frontend updates are frequent enough to avoid lag (Priority #2).
        We can drop frontend framerate if we need to
        """
        logger.debug(f"FrameRouter  process started!")
        video_recorder_manager: Optional[VideoRecorderManager] = None

        frame_rate_tracker = FrameRateTracker()
        try:
            while not kill_camera_group_flag.value:
                if frame_escape_pipe_exit.poll():
                    mf_payload = FrameRouterProcess._receive_multiframe(frame_escape_pipe_exit)
                    pulled_from_pipe_timestamp = time.perf_counter_ns()
                    mf_payload.lifespan_timestamps_ns.append({"received_in_frame_router": pulled_from_pipe_timestamp})
                    frame_rate_tracker.update(time.perf_counter_ns())

                    # TODO - Adapatively change the `resize` value based on performance metrics (i.e. shrink frontend-frames pipes/queues start filling up)

                    FrameRouterProcess._send_frontend_payload(frontend_relay_pipe=frontend_relay_pipe,
                                                              mf_payload=mf_payload,
                                                              backend_frame_rate=frame_rate_tracker.to_dict())

                    if record_frames_flag.value:
                        if not video_recorder_manager:  # create new video_recorder_manager on first multi-frame payload
                            video_recorder_manager = VideoRecorderManager.create(first_multi_frame_payload=mf_payload,
                                                                                 camera_configs=camera_configs,
                                                                                 recording_folder=create_recording_folder(
                                                                                     string_tag=None))
                            logger.info(
                                f"FrameRouter - Created FrameSaver for recording {video_recorder_manager.recording_name}")
                            # send  as bytes so it can use same ws/ relay as the frontend_payload's
                            recording_info = video_recorder_manager.recording_info
                            frontend_relay_pipe.send_bytes(recording_info.model_dump_json().encode('utf-8'))

                        # TODO - Decouple 'add_frame' from 'save_frame' and create a 'save_one_frame' method that saves a single frame from one camera, so we can check for new frames faster. We will need a mechanism to drain the buffers when recording ends
                        video_recorder_manager.add_multi_frame(mf_payload)

                    logger.loop(
                        f"FrameRouter - Finished processing multi-frame payload# {mf_payload.multi_frame_number}")
                else:
                    if video_recorder_manager:
                        if record_frames_flag.value:
                            video_recorder_manager.save_one_frame()
                        else:
                            logger.loop(
                                f"`Record frames flag is: `{record_frames_flag.value} and `video_recorder_manager` for recording {video_recorder_manager.recording_name} exists - Recording complete, shutting down recorder! ")
                            video_recorder_manager.finish_and_close()
                            video_recorder_manager = None
                    else:
                        wait_1ms()
        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
            logger.exception(e)
            raise
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if video_recorder_manager:
                video_recorder_manager.close()
            kill_camera_group_flag.value = True

    @staticmethod
    def _send_frontend_payload(frontend_relay_pipe: multiprocessing.Pipe,
                               mf_payload: MultiFramePayload,
                               backend_frame_rate:CurrentFrameRate):
        frontend_payload = FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf_payload,
                                                                         resize_image=.25,
                                                                         backend_frame_rate=backend_frame_rate)
        logger.loop(
            f"FrameRouter - Created FrontendFramePayload from multi-frame payload# {mf_payload.multi_frame_number}")
        # TODO - might/should be possible to send straight to GUI websocket client from here without the relay pipe? Maybe with ZeroMQ or SocketIO Assuming the relay pipe isn't faster (and that the GUI can unpack the bytes)
        logger.loop(f"FrameRouter - Sending FrontendFramePayload through frontend relay pipe...")
        frontend_relay_pipe.send_bytes(frontend_payload.model_dump_json().encode('utf-8'))
        logger.loop(f"FrameRouter - Sent FrontendFramePayload through frontend relay pipe!")

    @staticmethod
    def _receive_multiframe(frame_escape_pipe_exit: multiprocessing.Pipe) -> MultiFramePayload:
        logger.loop(f"FrameRouter - Receiving multi-frame bytes from pipe...")
        bytes_payload: bytes = frame_escape_pipe_exit.recv_bytes()
        if bytes_payload == b"START":
            mf_payload_bytes_list = []
            while True:
                if frame_escape_pipe_exit.poll():
                    bytes_payload = frame_escape_pipe_exit.recv_bytes()
                    mf_payload_bytes_list.append(bytes_payload)
                    if bytes_payload == b"END":
                        break
                else:
                    wait_1ms()
            mf_payload = MultiFramePayload.from_list(mf_payload_bytes_list)
        else:
            raise ValueError(f"FrameRouter - Received unexpected payload from pipe: {bytes_payload}")
        mf_payload.lifespan_timestamps_ns.append({"pulled_from_mf_queue": time.perf_counter_ns()})
        logger.loop(
            f"FrameRouter - Reconstructed multi-frame payload# {mf_payload.multi_frame_number} from pipe bytes!")
        return mf_payload
