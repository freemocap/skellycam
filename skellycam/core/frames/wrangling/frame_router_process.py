import logging
import multiprocessing
import time
from collections import deque
from typing import Optional

from skellycam.core.camera_group.camera_group_dto import CameraGroupDTO
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.videos.video_recorder_manager import VideoRecorderManager
from skellycam.system.default_paths import get_default_recording_folder_path
from skellycam.utilities.wait_functions import wait_100us

logger = logging.getLogger(__name__)


class FrameRouterProcess:
    def __init__(self,
                 dto: CameraGroupDTO,
                 frame_escape_pipe: multiprocessing.Pipe, ):

        self._process = multiprocessing.Process(target=self._run_process,
                                                name=self.__class__.__name__,
                                                args=(dto, frame_escape_pipe,))

    def start(self):
        logger.trace(f"Starting frame listener process")
        self._process.start()

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def join(self):
        self._process.join()

    @staticmethod
    def _run_process(dto: CameraGroupDTO,
                     frame_escape_pipe: multiprocessing.Pipe, ):
        """
        This process is not coupled to the frame loop, and the `escape pipe` is elastic, so blocking is not as big a sin here.
        MultiFrame chunks will be sent through the `frame_escape_pipe` and will be gathered, reconstructed into a framepayload, and handled here.
        """
        logger.debug(f"FrameRouter  process started!")
        incoming_mf_byte_chunklets = []
        mf_payloads_to_process: deque[MultiFramePayload] = deque()
        video_recorder_manager: Optional[VideoRecorderManager] = None
        try:
            while not dto.ipc_flags.kill_camera_group_flag.value and not dto.ipc_flags.global_kill_flag.value:
                wait_100us()

                # Check for incoming data
                if frame_escape_pipe.poll():
                    bytes_payload: bytes = frame_escape_pipe.recv_bytes()

                    if bytes_payload == b"START":
                        logger.loop(f"FrameRouter - Receiving START of a multi-frame bytes list from pipe...")
                    elif bytes_payload == b"END":
                        mf_payload = MultiFramePayload.from_list(incoming_mf_byte_chunklets)
                        incoming_mf_byte_chunklets = []
                        mf_payload.lifespan_timestamps_ns.append(
                            {"Reconstructed in FrameRouterProcess": time.perf_counter_ns()})
                        mf_payloads_to_process.append(mf_payload)
                        logger.loop(
                            f"FrameRouter - Reconstructed multi-frame payload# {mf_payload.multi_frame_number} from pipe bytes!")
                    else:
                        incoming_mf_byte_chunklets.append(bytes_payload)
                else:
                    if video_recorder_manager and video_recorder_manager.frames_to_save and not frame_escape_pipe.poll():  # prioritize other work before saving a frame
                        video_recorder_manager.save_one_frame()  # passes if empty

                # Handle multi-frame payloads
                if len(mf_payloads_to_process) > 0:
                    mf_payload = mf_payloads_to_process.popleft()
                    if dto.ipc_flags.record_frames_flag.value:
                        if not video_recorder_manager:
                            video_recorder_manager = VideoRecorderManager.create(camera_configs=dto.camera_configs,
                                                                                 recording_folder=get_default_recording_folder_path(
                                                                                     tag=""))
                            dto.ipc_queue.put(video_recorder_manager.recording_info)
                        video_recorder_manager.add_multi_frame(mf_payload)
                    else:
                        if video_recorder_manager:
                            logger.info('Recording complete, finishing and closing recorder...')
                            while len(mf_payloads_to_process) > 0:
                                video_recorder_manager.add_multi_frame(mf_payloads_to_process.popleft())
                            video_recorder_manager.finish_and_close()  # Note, this will block this process until all frames are written
                            video_recorder_manager = None
                    # TODO - send mf_payload along to the processing pipeline, somehow (maybe via another pipe? or the SharedMemoryIndexedArray thing i made?)


        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
            logger.exception(e)
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame exporter process error: {e} - Broken pipe error, problem in FrameListenerProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            logger.info(f"Frame exporter process received KeyboardInterrupt, shutting down gracefully...")
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            dto.ipc_flags.kill_camera_group_flag.value = True
            if video_recorder_manager:
                video_recorder_manager.finish_and_close()
