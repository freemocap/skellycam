import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from skellycam.utilities.wait_functions import wait_10ms

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
                                                     rec_info_sub_queue=ipc.pubsub.topics[TopicTypes.RECORDING_INFO].get_subscription(),
                                                     update_configs_sub_queue=ipc.pubsub.topics[TopicTypes.UPDATE_CONFIGS].get_subscription(),
                                                     update_shm_sub_queue=ipc.pubsub.topics[TopicTypes.SHM_UPDATES].get_subscription(),
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

        ipc.video_manager_status.is_running_flag.value = True
        recording_info_subscription = ipc.pubsub.recording_topic.get_subscription()

        camera_group_shm: CameraGroupSharedMemoryManager = CameraGroupSharedMemoryManager.recreate(
            shm_dto=group_shm_dto,
            read_only=False)

        recording_manager: RecordingManager | None = None
        audio_recorder: AudioRecorder | None = None
        logger.debug(f"FrameWrangler process started!")
        try:
            while ipc.should_continue:
                if ipc.video_manager_status.should_record.value:
                    recording_manager = VideoManager.start_recording(
                        ipc=ipc,
                        recording_info=recording_info_subscription.get(block=True),
                        recording_manager=recording_manager)

                    new_mfs = camera_group_shm.get_all_new_multiframes()
                    if len(new_mfs) > 0:
                        recording_manager.add_multi_frames(new_mfs)
                    else:
                        # if no new frames, opportunistically save one frame if we're recording
                        recording_manager.save_one_frame()
                else:
                    if recording_manager and not recording_manager.is_finished:
                        logger.debug(
                            f"Stopping RecordingManager `{recording_manager.recording_info.recording_name}`...")
                        ipc.video_manager_status.finishing.value = True
                        recording_manager.finish_and_close()
                        ipc.video_manager_status.finishing.value = False
                        recording_manager = None


        except Exception as e:
            ipc.video_manager_status.error.value = True
            logger.error(f"VideoManager process error: {e}")
            logger.exception(e)
            raise

        except KeyboardInterrupt:
            pass
        finally:
            ipc.video_manager_status.is_running_flag.value = False
            if recording_manager:
                recording_manager.finish_and_close()
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")

    @staticmethod
    def start_recording(ipc: CameraGroupIPC,
                        recording_info: RecordingInfo ,
                        recording_manager: RecordingManager | None) -> RecordingManager | None:
        if isinstance(recording_manager, RecordingManager):
            while not recording_manager.is_finished:
                logger.debug(f"Finishing RecordingManager `{recording_manager.recording_info.recording_name}`...")
                ipc.video_manager_status.finishing.value = True
                recording_manager.finish_and_close()
                ipc.video_manager_status.finishing.value = False


        if not isinstance(recording_info, RecordingInfo):
            raise ValueError(f"Expected RecordingInfo, got {type(recording_info)} in recording_info_queue")

        logger.debug(f"Creating RecodingManager for recording: `{recording_info.recording_name}`")
        ipc.video_manager_status.updating.value = True
        recording_manager = RecordingManager.create(
            recording_info=recording_info,
            camera_configs=ipc.camera_configs
        )
        ipc.video_manager_status.updating.value = False
        ipc.video_manager_status.is_recording_frames_flag.value = True
        return recording_manager

    @staticmethod
    def _should_pause(ipc):
        if ipc.should_pause_flag.value:
            logger.debug("Multiframe publication paused")
            ipc.video_manager_status.is_paused_flag.value = True
            return True
        else:
            ipc.video_manager_status.is_paused_flag.value = False
            return False
