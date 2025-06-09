import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateShmMessage, UpdateCameraConfigsMessage, RecordingInfoMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_manager import VideoManager
from skellycam.core.types import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)


class RecordingManager(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    worker: multiprocessing.Process
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO):
        return cls(
            ipc=ipc,
            worker=multiprocessing.Process(target=cls._video_worker,
                                           name=cls.__class__.__name__,
                                           kwargs=dict(ipc=ipc,
                                                       group_shm_dto=group_shm_dto,
                                                       camera_configs=ipc.camera_configs,
                                                       update_configs_sub_queue=ipc.pubsub.topics[
                                                           TopicTypes.UPDATE_CONFIGS].get_subscription(),
                                                       recording_info_subscription_queue=ipc.pubsub.topics[
                                                           TopicTypes.RECORDING_INFO].get_subscription(),
                                                       shm_subscription_queue=ipc.pubsub.topics[
                                                           TopicTypes.SHM_UPDATES].get_subscription(),

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
    def _video_worker(cls,
                      ipc: CameraGroupIPC,
                      group_shm_dto: CameraGroupSharedMemoryDTO,
                      recording_info_subscription_queue: TopicSubscriptionQueue,
                      shm_subscription_queue: TopicSubscriptionQueue,
                      update_configs_sub_queue: TopicSubscriptionQueue,
                      camera_configs: CameraConfigs,
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
        ipc.video_manager_status.is_running_flag.value = True
        logger.success(f"VideoManager process started for camera group `{ipc.group_id}`")
        try:
            while ipc.should_continue:
                if ipc.should_pause_flag.value:
                    logger.debug(f"VideoManager process paused for camera group `{ipc.group_id}`")
                    ipc.video_manager_status.is_paused_flag.value = True
                    wait_10ms()
                    continue
                ipc.video_manager_status.is_paused_flag.value = False
                video_manager = cls._drain_and_handle_mf_buffer(
                    ipc=ipc,
                    video_manager=video_manager,
                    camera_group_shm=camera_group_shm
                )
                camera_configs, camera_group_shm, video_manager = cls._check_and_handle_updates(
                    ipc=ipc,
                    camera_configs=camera_configs,
                    video_manager=video_manager,
                    camera_group_shm=camera_group_shm,
                    shm_subscription_queue=shm_subscription_queue,
                    update_configs_sub_queue=update_configs_sub_queue,
                    recording_info_subscription_queue=recording_info_subscription_queue
                )



        except Exception as e:
            ipc.kill_everything()
            ipc.video_manager_status.error.value = True
            logger.error(f"{cls.__class__.__name__} process error: {e}")
            logger.exception(e)
            raise

        except KeyboardInterrupt:
            pass
        finally:
            ipc.video_manager_status.is_running_flag.value = False
            if video_manager:
                video_manager.finish_and_close()
            camera_group_shm.close()
            logger.debug(f"FrameSaver process completed")

    @classmethod
    def _drain_and_handle_mf_buffer(cls,
                                    ipc: CameraGroupIPC,
                                    video_manager: VideoManager | None,
                                    camera_group_shm: CameraGroupSharedMemoryManager) -> VideoManager | None:
        new_mfs = camera_group_shm.get_all_new_multiframes(
            invalid_ok=True)  # prioritize draining shm each loop to avoid overwriting on the ring buffer

        if len(new_mfs) > 0 and video_manager is not None:
            print(f"VideoManager: {len(new_mfs)} new frames to process")
            # if new frames, add them to the recording manager (doesn't save them yet)
            video_manager.add_multi_frames(new_mfs)
        else:
            if video_manager:
                if ipc.video_manager_status.should_record.value:
                    # if we're recording and there are no new frames, opportunistically save one frame if we're recording
                    video_manager.save_one_frame()
                else:
                    # if we have a video manager but not recording, then finish and close it
                    video_manager = cls.stop_recording(ipc=ipc, video_manager=video_manager)
        return video_manager

    @classmethod
    def _check_and_handle_updates(cls,
                                  ipc: CameraGroupIPC,
                                  camera_configs: CameraConfigs,
                                  video_manager: VideoManager | None,
                                  camera_group_shm: CameraGroupSharedMemoryManager,
                                  shm_subscription_queue: multiprocessing.Queue,
                                  update_configs_sub_queue: multiprocessing.Queue,
                                  recording_info_subscription_queue: multiprocessing.Queue) -> tuple[
        CameraConfigs, CameraGroupSharedMemoryManager, VideoManager | None,]:
        if not update_configs_sub_queue.empty():
            update_configs_message = update_configs_sub_queue.get(block=True)
            if not isinstance(update_configs_message, UpdateCameraConfigsMessage):
                raise ValueError(
                    f"Expected UpdateCameraConfigsMessage, got {type(update_configs_message)} in update_configs_sub_queue")
            camera_configs = update_configs_message.new_configs
        if not recording_info_subscription_queue.empty():
            ipc.video_manager_status.updating.value = True
            recording_info_msg = recording_info_subscription_queue.get(block=True)
            if isinstance(recording_info_msg, RecordingInfoMessage):
                if video_manager is not None:
                    logger.warning("VideoManager already exists, finishing it before starting a new one.")
                    video_manager.finish_and_close()
                video_manager = cls.start_recording(ipc=ipc,
                                                    recording_info=recording_info_msg.recording_info,
                                                    camera_configs=camera_configs,
                                                    video_manager=video_manager)
            else:
                raise ValueError(
                    f"Expected RecordingInfoMessage, got {type(recording_info_msg)} in recording_info_queue")
            ipc.video_manager_status.updating.value = False

        if not shm_subscription_queue.empty():
            if video_manager is not None or ipc.any_recording:
                video_manager.finish_and_close()
                video_manager = None
            ipc.video_manager_status.updating.value = True
            shm_update = shm_subscription_queue.get(block=True)
            if not isinstance(shm_update, UpdateShmMessage):
                raise ValueError(f"Expected ShmUpdateMessage, got {type(shm_update)} in shm_subscription_queue")
            camera_group_shm.close()  # close but don't unlink - that's the original shm's job
            camera_group_shm = CameraGroupSharedMemoryManager.recreate(
                shm_dto=shm_update.group_shm_dto,
                read_only=camera_group_shm.read_only)
            ipc.video_manager_status.updating.value = False

        return camera_configs, camera_group_shm, video_manager

    @staticmethod
    def start_recording(ipc: CameraGroupIPC,
                        recording_info: RecordingInfo,
                        camera_configs: CameraConfigs,
                        video_manager: VideoManager | None) -> VideoManager | None:
        if isinstance(video_manager, VideoManager):
            while not video_manager.is_finished:
                logger.debug(f"Finishing VideoManager `{video_manager.recording_info.recording_name}`...")
                ipc.video_manager_status.finishing.value = True
                video_manager.finish_and_close()
                ipc.video_manager_status.finishing.value = False

        if not isinstance(recording_info, RecordingInfo):
            raise ValueError(f"Expected RecordingInfo, got {type(recording_info)} in recording_info_queue")
        if not isinstance(camera_configs, dict) or any(
                [not isinstance(config, CameraConfig) for config in camera_configs.values()]):
            raise ValueError(f"Expected CameraConfigs, got {type(camera_configs)} in camera_configs")

        logger.debug(f"Creating RecodingManager for recording: `{recording_info.recording_name}`")
        ipc.video_manager_status.updating.value = True
        video_manager = VideoManager.create(recording_info=recording_info,
                                            camera_configs=camera_configs,
                                            )
        ipc.video_manager_status.updating.value = False
        ipc.video_manager_status.is_recording_frames_flag.value = True
        return video_manager

    @staticmethod
    def stop_recording(ipc: CameraGroupIPC,video_manager: VideoManager) -> None:
        logger.debug(f"Stopping recording: `{video_manager.recording_info.recording_name}`...")
        if not isinstance(video_manager, VideoManager):
            raise ValueError(f"Expected VideoManager, got {type(video_manager)} in video_manager")
        ipc.video_manager_status.is_recording_frames_flag.value = False

        ipc.video_manager_status.finishing.value = True
        video_manager.finish_and_close()
        ipc.video_manager_status.finishing.value = False

        return None
