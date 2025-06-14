import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict, SkipValidation

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import DeviceExtractedConfigMessage, SetShmMessage, RecordingInfoMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager_status import RecordingManagerStatus
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_manager import VideoManager
from skellycam.core.types import TopicSubscriptionQueue, CameraIdString, WorkerType, WorkerStrategy

logger = logging.getLogger(__name__)


class RecordingManager(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    worker: WorkerType
    ipc: CameraGroupIPC
    should_close_self: SkipValidation[multiprocessing.Value]

    @property
    def status(self):
        return self.ipc.recording_manager_status

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               camera_ids: list[CameraIdString],
               worker_strategy: WorkerStrategy):
        should_close_self = multiprocessing.Value("b", False)
        return cls(
            ipc=ipc,
            should_close_self=should_close_self,
            worker=worker_strategy.value(target=cls._worker,
                                         name=cls.__class__.__name__,
                                         kwargs=dict(ipc=ipc,
                                                     camera_ids=camera_ids,
                                                     should_close_self=should_close_self,
                                                     recording_info_subscription=ipc.pubsub.topics[
                                                         TopicTypes.RECORDING_INFO].get_subscription(),
                                                     config_updates_subscription=ipc.pubsub.topics[
                                                         TopicTypes.EXTRACTED_CONFIG].get_subscription(),
                                                     shm_updates_subscription=ipc.pubsub.topics[
                                                         TopicTypes.SHM_UPDATES].get_subscription(),

                                                     )),
        )

    def start(self):
        logger.debug(f"Starting video worker process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def join(self):
        self.worker.join()

    @property
    def ready(self):
        return self.worker.is_alive()

    def close(self):
        logger.debug(f"Closing video worker process...")
        self.should_close_self.value = False
        if self.is_alive():
            self.join()
        logger.debug(f"Video worker closed")

    @classmethod
    def _worker(cls,
                ipc: CameraGroupIPC,
                camera_ids: list[CameraIdString],
                recording_info_subscription: TopicSubscriptionQueue,
                config_updates_subscription: TopicSubscriptionQueue,
                shm_updates_subscription: TopicSubscriptionQueue,
                should_close_self: multiprocessing.Value
                ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
        def should_continue():
            return ipc.should_continue and not should_close_self.value
        status: RecordingManagerStatus = ipc.recording_manager_status
        camera_group_shm: CameraGroupSharedMemoryManager | None = None
        camera_configs: dict[CameraIdString, CameraConfig | None] = {camera_id: None for camera_id in camera_ids}
        while should_continue() and (
                camera_group_shm is None or any([config is None for config in camera_configs.values()])):
            if not config_updates_subscription.empty():
                config_message = config_updates_subscription.get()
                if not isinstance(config_message, DeviceExtractedConfigMessage):
                    raise RuntimeError(
                        f"Expected DeviceExtractedConfigMessage, got {type(config_message)} in config_updates_subscription"
                    )
                camera_configs[config_message.extracted_config.camera_id] = config_message.extracted_config
            if not shm_updates_subscription.empty():
                shm_message = shm_updates_subscription.get()
                if not isinstance(shm_message, SetShmMessage):
                    raise RuntimeError(
                        f"Expected CameraGroupSharedMemoryManager, got {type(shm_message)} in shm_updates_subscription"
                    )
                camera_group_shm = CameraGroupSharedMemoryManager.recreate(
                    shm_dto=shm_message.camera_group_shm_dto,
                    read_only=False
                )

        # Ensure camera_group_shm is properly initialized before proceeding
        if camera_group_shm is None or not camera_group_shm.valid:
            raise RuntimeError("Failed to initialize camera_group_shm")

        #Ensure all camera configs are properly initialized before proceeding
        if any([config is None for config in camera_configs.values()]):
            raise RuntimeError(f"Failed to initialize camera_configs: {camera_configs}")

        video_manager: VideoManager | None = None
        audio_recorder: AudioRecorder | None = None
        latest_mf: MultiFramePayload | None = None
        status.is_running_flag.value = True
        logger.success(f"VideoManager process started for camera group `{ipc.group_id}`")
        try:
            while should_continue():
                # check for new recording info
                if not recording_info_subscription.empty():
                    recording_info_message = recording_info_subscription.get()
                    if not isinstance(recording_info_message, RecordingInfoMessage):
                        raise RuntimeError(
                            f"Expected RecordingInfo, got {type(recording_info_message)} in recording_info_subscription"
                        )

                    video_manager = cls.start_recording(status=status,
                                                        recording_info=recording_info_message.recording_info,
                                                        camera_configs=camera_configs,
                                                        video_manager=video_manager)

                # check for config updates
                if not config_updates_subscription.empty():
                    if status.recording:
                        raise NotImplementedError("Config updates during recording are not implemented.")
                    config_message = config_updates_subscription.get()
                    if not isinstance(config_message, DeviceExtractedConfigMessage):
                        raise RuntimeError(
                            f"Expected DeviceExtractedConfigMessage, got {type(config_message)} in config_updates_subscription"
                        )
                    camera_configs[config_message.extracted_config.camera_id] = config_message.extracted_config

                # check for shared memory updates
                if not shm_updates_subscription.empty():
                    raise NotImplementedError("Runtime updates of shared memory are not yet implemented.")

                # check/handle new multi-frames
                video_manager, latest_mf = cls._get_and_handle_new_mfs(
                    status=status,
                    camera_configs=camera_configs,
                    video_manager=video_manager,
                    camera_group_shm=camera_group_shm,
                    latest_mf=latest_mf
                )

        except Exception as e:
            status.error.value = True
            ipc.kill_everything()
            logger.error(f"{cls.__class__.__name__} process error: {e}")
            logger.exception(e)
            raise

        except KeyboardInterrupt:
            pass
        finally:
            status.is_running_flag.value = False
            should_close_self.value = True
            if video_manager:
                video_manager.finish_and_close()
            camera_group_shm.close()
            logger.debug(f"RecordingManager worker completed")

    @classmethod
    def _get_and_handle_new_mfs(cls,
                                status: RecordingManagerStatus,
                                camera_configs: CameraConfigs,
                                video_manager: VideoManager | None,
                                latest_mf: MultiFramePayload | None,
                                camera_group_shm: CameraGroupSharedMemoryManager) -> tuple[
        VideoManager | None, MultiFramePayload | None]:
        latest_mfs = camera_group_shm.multi_frame_ring_shm.get_all_new_multiframes(camera_configs=camera_configs)
        status.total_frames_published.value += len(latest_mfs)
        status.number_frames_published_this_cycle.value = len(latest_mfs)

        if len(latest_mfs) > 0 and video_manager is not None:
            print(f"VideoManager: {len(latest_mfs)} new frames to process")
            latest_mf = latest_mfs[-1]
            # if new frames, add them to the recording manager (doesn't save them yet)
            video_manager.add_multi_frames(latest_mfs)
        else:
            if video_manager:
                if status.should_record.value:
                    # if we're recording and there are no new frames, opportunistically save one frame if we're recording
                    video_manager.save_one_frame()
                else:
                    # if we have a video manager but not recording, then finish and close it
                    video_manager = cls.stop_recording(status=status, video_manager=video_manager)
        return video_manager, latest_mf

    @classmethod
    def start_recording(cls,
                        status: RecordingManagerStatus,
                        recording_info: RecordingInfo,
                        camera_configs: CameraConfigs,
                        video_manager: VideoManager | None) -> VideoManager | None:
        if isinstance(video_manager, VideoManager):
            cls.stop_recording(status=status, video_manager=video_manager)

        if not isinstance(recording_info, RecordingInfo):
            raise ValueError(f"Expected RecordingInfo, got {type(recording_info)} in recording_info_queue")
        if not isinstance(camera_configs, dict) or any(
                [not isinstance(config, CameraConfig) for config in camera_configs.values()]):
            raise ValueError(f"Expected CameraConfigs, got {type(camera_configs)} in camera_configs")

        logger.debug(f"Creating RecodingManager for recording: `{recording_info.recording_name}`")
        status.updating.value = True
        video_manager = VideoManager.create(recording_info=recording_info,
                                            camera_configs=camera_configs,
                                            )
        status.updating.value = False
        status.is_recording_frames_flag.value = True
        return video_manager

    @classmethod
    def stop_recording(cls, status: RecordingManagerStatus, video_manager: VideoManager) -> None:
        logger.debug(f"Stopping recording: `{video_manager.recording_info.recording_name}`...")
        if not isinstance(video_manager, VideoManager):
            raise ValueError(f"Expected VideoManager, got {type(video_manager)} in video_manager")
        status.is_recording_frames_flag.value = False

        status.finishing.value = True
        video_manager.finish_and_close()
        status.finishing.value = False

        return None
