import logging
import multiprocessing
import time
from typing import Optional

from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO, CameraGroupSharedMemory
from skellycam.core.timestamps.frame_rate_tracker import FrameRateTracker
from skellycam.core.videos.video_recorder_manager import VideoRecorderManager
from skellycam.system.default_paths import create_recording_folder
from skellycam.utilities.wait_functions import wait_1ms, wait_1us

logger = logging.getLogger(__name__)


class FrameRouterProcess:
    def __init__(self,
                 group_shm_dto: CameraGroupSharedMemoryDTO,
                 new_mf_ready_flag: multiprocessing.Value,
                 ipc_queue: multiprocessing.Queue,
                 record_frames_flag: multiprocessing.Value,
                 kill_camera_group_flag: multiprocessing.Value, ):

        self.process = multiprocessing.Process(target=self._run_process,
                                               name=self.__class__.__name__,
                                               args=(group_shm_dto,
                                                     new_mf_ready_flag,
                                                     ipc_queue,
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
    def _run_process(group_shm_dto: CameraGroupSharedMemoryDTO,
                     new_mf_ready_flag: multiprocessing.Value,
                     ipc_queue: multiprocessing.Queue,
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
        camera_group_shm = CameraGroupSharedMemory.recreate(dto=group_shm_dto)
        frame_rate_tracker = FrameRateTracker()
        mf_payload: Optional[MultiFramePayload] = None
        try:
            while not kill_camera_group_flag.value:
                if new_mf_ready_flag.value:
                    mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload,
                                                                          read_only=False)
                    new_mf_ready_flag.value = False
                    pulled_from_pipe_timestamp = time.perf_counter_ns()
                    mf_payload.lifespan_timestamps_ns.append({"received_in_frame_router": pulled_from_pipe_timestamp})
                    frame_rate_tracker.update(pulled_from_pipe_timestamp)
                    ipc_queue.put(frame_rate_tracker.current())
                    if record_frames_flag.value:
                        if not video_recorder_manager:
                            video_recorder_manager = VideoRecorderManager.create(first_multi_frame_payload=mf_payload,
                                                                                 camera_configs=group_shm_dto.camera_configs,
                                                                                 recording_folder=create_recording_folder(
                                                                                     string_tag=None))
                            logger.info(
                                f"FrameRouter - Created FrameSaver for recording {video_recorder_manager.recording_name}")
                            recording_info = video_recorder_manager.recording_info
                            ipc_queue.put(recording_info)

                        video_recorder_manager.add_multi_frame(mf_payload)

                    logger.loop(
                        f"FrameRouter - Finished processing multi-frame payload# {mf_payload.multi_frame_number}")
                else:
                    if video_recorder_manager:
                        if record_frames_flag.value:
                            video_recorder_manager.save_one_frame()
                        else:
                            logger.info(
                                f"`Record frames flag is: `{record_frames_flag.value} and `video_recorder_manager` for recording {video_recorder_manager.recording_name} exists - Recording complete, shutting down recorder! ")
                            video_recorder_manager.finish_and_close()
                            logger.info(f"FrameRouter - Finished recording {video_recorder_manager.recording_name}")
                            video_recorder_manager = None
                    else:
                        wait_1us()

        except Exception as e:
            logger.error(f"Frame exporter process error: {e}")
            logger.exception(e)
            raise
        finally:
            logger.trace(f"Stopped listening for multi-frames")
            if video_recorder_manager:
                video_recorder_manager.close()
            kill_camera_group_flag.value = True
            new_mf_ready_flag.value = False

    @staticmethod
    def _receive_multiframe(frame_escape_pipe_exit: multiprocessing.Pipe) -> MultiFramePayload:
        logger.loop(f"FrameRouter - Receiving multi-frame bytes from pipe...")
        bytes_payload: bytes = frame_escape_pipe_exit.recv_bytes()
        if not bytes_payload == b"START":
            raise ValueError(f"FrameRouter - Received unexpected payload from pipe: {bytes_payload}")

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

        mf_payload.lifespan_timestamps_ns.append({"pulled_from_mf_queue": time.perf_counter_ns()})
        logger.loop(
            f"FrameRouter - Reconstructed multi-frame payload# {mf_payload.multi_frame_number} from pipe bytes!")
        return mf_payload
