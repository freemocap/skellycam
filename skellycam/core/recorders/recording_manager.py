import enum
import logging
import multiprocessing
import threading

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_manager import VideoManager
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class CameraWorkerStrategies(enum.Enum):
    THREAD = enum.auto()
    PROCESS = enum.auto()


class RecordingManager(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    worker: multiprocessing.Process | threading.Thread
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO,
                camera_configs: CameraConfigs,
               recording_worker_strategy: CameraWorkerStrategies = CameraWorkerStrategies.THREAD, ):
        if recording_worker_strategy == CameraWorkerStrategies.PROCESS:
            worker_maker = multiprocessing.Process
        elif recording_worker_strategy == CameraWorkerStrategies.THREAD:
            worker_maker = threading.Thread
        else:
            raise ValueError(f"Unsupported camera worker strategy: {recording_worker_strategy}")

        return cls(
            ipc=ipc,
            worker=worker_maker(target=cls._worker,
                                name=cls.__class__.__name__,
                                kwargs=dict(ipc=ipc,
                                            group_shm_dto=group_shm_dto,
                                            camera_configs=camera_configs,
                                            )
                                ),
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

    @classmethod
    def _worker(cls,
                ipc: CameraGroupIPC,
                camera_configs: CameraConfigs,
                group_shm_dto: CameraGroupSharedMemoryDTO,
                ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)

        camera_group_shm: CameraGroupSharedMemoryManager = CameraGroupSharedMemoryManager.recreate(
            shm_dto=group_shm_dto,
            read_only=False)
        video_manager: VideoManager | None = None
        audio_recorder: AudioRecorder | None = None
        latest_mf: MultiFramePayload | None = None
        ipc.recording_manager_status.is_running_flag.value = True
        logger.success(f"VideoManager process started for camera group `{ipc.group_id}`")
        try:
            while ipc.should_continue:
                if ipc.should_pause_flag.value:
                    ipc.recording_manager_status.is_paused_flag.value = True
                    wait_10ms()
                    continue
                ipc.recording_manager_status.is_paused_flag.value = False

                video_manager, latest_mf = cls._get_and_handle_new_mfs(
                    ipc=ipc,
                    video_manager=video_manager,
                    camera_group_shm=camera_group_shm,
                    latest_mf=latest_mf
                )



        except Exception as e:
            ipc.kill_everything()
            ipc.recording_manager_status.error.value = True
            logger.error(f"{cls.__class__.__name__} process error: {e}")
            logger.exception(e)
            raise

        except KeyboardInterrupt:
            pass
        finally:
            ipc.recording_manager_status.is_running_flag.value = False
            if video_manager:
                video_manager.finish_and_close()
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")

    @classmethod
    def _get_and_handle_new_mfs(cls,
                                ipc: CameraGroupIPC,
                                video_manager: VideoManager | None,
                                latest_mf: MultiFramePayload | None,
                                camera_group_shm: CameraGroupSharedMemoryManager) -> tuple[
        VideoManager | None, MultiFramePayload | None]:
        latest_mfs = camera_group_shm.build_all_new_multiframes(previous_payload=latest_mf,
                                                                overwrite=False)
        ipc.recording_manager_status.total_frames_published.value += len(latest_mfs)
        ipc.recording_manager_status.number_frames_published_this_cycle.value = len(latest_mfs)
        if latest_mfs:
            latest_mf = latest_mfs[-1]
        if len(latest_mfs) > 0 and video_manager is not None:
            print(f"VideoManager: {len(latest_mfs)} new frames to process")
            # if new frames, add them to the recording manager (doesn't save them yet)
            video_manager.add_multi_frames(latest_mfs)
        else:
            if video_manager:
                if ipc.recording_manager_status.should_record.value:
                    # if we're recording and there are no new frames, opportunistically save one frame if we're recording
                    video_manager.save_one_frame()
                else:
                    # if we have a video manager but not recording, then finish and close it
                    video_manager = cls.stop_recording(ipc=ipc, video_manager=video_manager)
        return video_manager, latest_mf


    @staticmethod
    def start_recording(ipc: CameraGroupIPC,
                        recording_info: RecordingInfo,
                        camera_configs: CameraConfigs,
                        video_manager: VideoManager | None) -> VideoManager | None:
        if isinstance(video_manager, VideoManager):
            while not video_manager.is_finished:
                logger.debug(f"Finishing VideoManager `{video_manager.recording_info.recording_name}`...")
                ipc.recording_manager_status.finishing.value = True
                video_manager.finish_and_close()
                ipc.recording_manager_status.finishing.value = False

        if not isinstance(recording_info, RecordingInfo):
            raise ValueError(f"Expected RecordingInfo, got {type(recording_info)} in recording_info_queue")
        if not isinstance(camera_configs, dict) or any(
                [not isinstance(config, CameraConfig) for config in camera_configs.values()]):
            raise ValueError(f"Expected CameraConfigs, got {type(camera_configs)} in camera_configs")

        logger.debug(f"Creating RecodingManager for recording: `{recording_info.recording_name}`")
        ipc.recording_manager_status.updating.value = True
        video_manager = VideoManager.create(recording_info=recording_info,
                                            camera_configs=camera_configs,
                                            )
        ipc.recording_manager_status.updating.value = False
        ipc.recording_manager_status.is_recording_frames_flag.value = True
        return video_manager

    @staticmethod
    def stop_recording(ipc: CameraGroupIPC, video_manager: VideoManager) -> None:
        logger.debug(f"Stopping recording: `{video_manager.recording_info.recording_name}`...")
        if not isinstance(video_manager, VideoManager):
            raise ValueError(f"Expected VideoManager, got {type(video_manager)} in video_manager")
        ipc.recording_manager_status.is_recording_frames_flag.value = False

        ipc.recording_manager_status.finishing.value = True
        video_manager.finish_and_close()
        ipc.recording_manager_status.finishing.value = False

        return None
