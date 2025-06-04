import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.types import RecordingManagerIdString
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


@dataclass
class VideoManager:
    worker: multiprocessing.Process
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO):
        worker = multiprocessing.Process(target=cls._mf_subscription_video_worker,
                                         name=cls.__class__.__name__,
                                         kwargs=dict(ipc=ipc,
                                                     group_shm_dto=group_shm_dto,
                                                     ws_logs_queue=get_websocket_log_queue()
                                                     )
                                         )
        return cls(worker=worker,
                   ipc=ipc,
                   )

    def start(self):
        logger.debug(f"Starting video worker process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self):
        self.worker.join()

    def close(self):
        logger.debug(f"Closing video worker process...")
        self.ipc.should_continue = False
        if self.is_alive():
            self.join()
        logger.debug(f"Video worker closed")

    @staticmethod
    def _mf_subscription_video_worker(ipc: CameraGroupIPC,
                                      group_shm_dto: CameraGroupSharedMemoryDTO,
                                      ws_logs_queue: multiprocessing.Queue
                                      ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ws_logs_queue)

        camera_group_shm: CameraGroupSharedMemoryManager = CameraGroupSharedMemoryManager.recreate_from_dto(
            ipc=ipc,
            shm_dto=group_shm_dto,
            read_only=False)

        recording_manager: RecordingManager | None = None
        audio_recorder: AudioRecorder | None = None
        latest_mf: MultiFramePayload | None = None
        logger.debug(f"FrameWrangler process started!")
        try:
            while ipc.should_continue:
                # Check for new recording info
                recording_manager = VideoManager.check_recording_info_queue(ipc=ipc,
                                                                            latest_mf=latest_mf,
                                                                            recording_manager=recording_manager)

                latest_mf = VideoManager.get_and_handle_new_mfs(camera_group_shm=camera_group_shm,
                                                                latest_mf=latest_mf,
                                                                recording_manager=recording_manager)


        except Exception as e:
            logger.error(f"Frame Saver process error: {e}")
            logger.exception(e)
            raise
        except BrokenPipeError as e:
            logger.error(f"Frame Saver process error: {e} - Broken pipe error, problem in FrameListenerProcess?")
            logger.exception(e)
            raise
        except KeyboardInterrupt:
            pass
        finally:
            if recording_manager:
                    recording_manager.finish_and_close()
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")

    @staticmethod
    def get_and_handle_new_mfs(camera_group_shm:CameraGroupSharedMemoryManager,
                               latest_mf:MultiFramePayload|None,
                               recording_manager:RecordingManager|None) -> MultiFramePayload|None:
        # Get and handle new mfs
        new_mfs = camera_group_shm.get_all_new_multiframes()
        if len(new_mfs) > 0 and isinstance(new_mfs[-1], MultiFramePayload):
            if latest_mf is None:
                logger.debug(f"Pulled first multiframe(s) from camera group: {new_mfs[-1].camera_ids}")
            latest_mf = new_mfs[-1]
            if recording_manager:
                recording_manager.add_multi_frames(new_mfs)
        else:
            # if no new frames, opportunistically save one frame if we're recording
            if recording_manager:
                recording_manager.save_one_frame()
        return latest_mf

    @staticmethod
    def check_recording_info_queue(ipc:CameraGroupIPC,
                                   latest_mf:MultiFramePayload|None,
                                   recording_manager:RecordingManager|None) -> RecordingManager|None:
        if not ipc.recording_info_queue.empty() and latest_mf:
            recording_info = ipc.recording_info_queue.get()
            if isinstance(recording_info, RecordingInfo) and recording_info is not None:
                logger.debug(f"Creating RecodingManager for recording: `{recording_info.recording_name}`")
                ipc.recording_frames_flag.value = True
                recording_manager = RecordingManager.create(
                    recording_info=recording_info,
                    initial_multi_frame_payload=latest_mf,
                )
            elif recording_info is None:
                if recording_manager is not None:
                    logger.info(f"Stopping recording for {recording_manager.recording_info.recording_name}...")
                    recording_manager.finish_and_close()
                    recording_manager = None
                ipc.recording_frames_flag.value = False
            else:
                raise ValueError(f"Unexpected type in recording_info_queue: {type(recording_info)}")
        else:
            wait_1ms()
        return recording_manager
