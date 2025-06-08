import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateShmMessage, UpdateCameraConfigsMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO, \
    CameraGroupSharedMemoryManager
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager import RecordingManager
from skellycam.core.recorders.videos.recording_info import RecordingInfo

logger = logging.getLogger(__name__)


class VideoManager(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    worker: multiprocessing.Process
    ipc: CameraGroupIPC

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               group_shm_dto: CameraGroupSharedMemoryDTO):
        worker = multiprocessing.Process(target=cls._video_worker,
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

    @classmethod
    def _video_worker(cls,
                      ipc: CameraGroupIPC,
                      group_shm_dto: CameraGroupSharedMemoryDTO,
                      recording_info_subscription_queue: multiprocessing.Queue,
                      shm_subscription_queue: multiprocessing.Queue,
                      update_configs_sub_queue: multiprocessing.Queue,
                      camera_configs: CameraConfigs,

                      ):
        # Configure logging in the child process
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)

        camera_group_shm: CameraGroupSharedMemoryManager = CameraGroupSharedMemoryManager.recreate(
            shm_dto=group_shm_dto,
            read_only=False)

        if not isinstance(camera_group_shm, CameraGroupSharedMemoryManager):
            raise ValueError(f"Expected CameraConfigs, got {type(camera_group_shm)} in camera_configs")

        recording_manager: RecordingManager | None = None
        audio_recorder: AudioRecorder | None = None
        ipc.video_manager_status.is_running_flag.value = True
        logger.success(f"VideoManager process started for camera group `{ipc.group_id}`")
        try:
            while ipc.should_continue:
                recording_manager = cls._drain_and_handle_mf_buffer(
                    ipc=ipc,
                    recording_manager=recording_manager,
                    camera_group_shm=camera_group_shm
                )
                camera_configs, recording_manager, camera_group_shm = cls._check_and_handle_updates(
                    ipc=ipc,
                    camera_configs=camera_configs,
                    recording_manager=recording_manager,
                    camera_group_shm=camera_group_shm,
                    shm_subscription_queue=shm_subscription_queue,
                    update_configs_sub_queue=update_configs_sub_queue,
                    recording_info_subscription_queue=recording_info_subscription_queue
                )



        except Exception as e:
            ipc.should_continue = False
            ipc.video_manager_status.error.value = True
            logger.error(f"{cls.__class__.__name__} process error: {e}")
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

    @classmethod
    def _drain_and_handle_mf_buffer(cls,
                                    ipc: CameraGroupIPC,
                                    recording_manager: RecordingManager | None,
                                    camera_group_shm: CameraGroupSharedMemoryManager) -> RecordingManager | None:
        new_mfs = camera_group_shm.get_all_new_multiframes(
            invalid_ok=True)  # prioritize draining shm each loop to avoid overwriting on the ring buffer

        if len(new_mfs) > 0 and recording_manager is not None:
            print(f"VideoManager: {len(new_mfs)} new frames to process")
            # if new frames, add them to the recording manager (doesn't save them yet)
            recording_manager.add_multi_frames(new_mfs)
        else:
            if recording_manager:
                # if no new frames and we're recording, opportunistically save one frame if we're recording
                recording_manager.save_one_frame()

        if not ipc.video_manager_status.should_record.value and recording_manager:
            recording_manager = cls.stop_recording(
                ipc=ipc,
                recording_manager=recording_manager
            )
        return recording_manager

    @classmethod
    def _check_and_handle_updates(cls,
                                  ipc: CameraGroupIPC,
                                  camera_configs: CameraConfigs,
                                  recording_manager: RecordingManager | None,
                                  camera_group_shm: CameraGroupSharedMemoryManager,
                                  shm_subscription_queue: multiprocessing.Queue,
                                  update_configs_sub_queue: multiprocessing.Queue,
                                  recording_info_subscription_queue: multiprocessing.Queue) -> tuple[
        CameraConfigs, CameraGroupSharedMemoryManager, RecordingManager | None, ]:
        if not update_configs_sub_queue.empty():
            update_configs_message = update_configs_sub_queue.get(block=True)
            if not isinstance(update_configs_message, UpdateCameraConfigsMessage):
                raise ValueError(
                    f"Expected UpdateCameraConfigsMessage, got {type(update_configs_message)} in update_configs_sub_queue")
            camera_configs = update_configs_message.new_configs
        if not recording_info_subscription_queue.empty():
            ipc.video_manager_status.updating.value = True
            recording_info = recording_info_subscription_queue.get(block=True)
            if isinstance(recording_info, RecordingInfo):
                if recording_manager is not None:
                    logger.warning("RecordingManager already exists, finishing it before starting a new one.")
                    recording_manager.finish_and_close()
                recording_manager = cls.start_recording(ipc=ipc,
                                                        recording_info=recording_info,
                                                        recording_manager=recording_manager)
            else:
                raise ValueError(f"Expected RecordingInfo, got {type(recording_info)} in recording_info_queue")
            ipc.video_manager_status.updating.value = False

        if not shm_subscription_queue.empty():
            if recording_manager is not None or ipc.any_recording:
                recording_manager.finish_and_close()
                recording_manager = None
            ipc.video_manager_status.updating.value = True
            shm_update = shm_subscription_queue.get(block=True)
            if not isinstance(shm_update, UpdateShmMessage):
                raise ValueError(f"Expected ShmUpdateMessage, got {type(shm_update)} in shm_subscription_queue")
            camera_group_shm.close()  # close but don't unlink - that's the original shm's job
            camera_group_shm = CameraGroupSharedMemoryManager.recreate(
                shm_dto=shm_update.group_shm_dto,
                read_only=camera_group_shm.read_only)
            ipc.video_manager_status.updating.value = False

        return camera_configs, camera_group_shm,recording_manager

    @staticmethod
    def start_recording(ipc: CameraGroupIPC,
                        recording_info: RecordingInfo,
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
        )
        ipc.video_manager_status.updating.value = False
        ipc.video_manager_status.is_recording_frames_flag.value = True
        return recording_manager

    @staticmethod
    def stop_recording(ipc: CameraGroupIPC,
                       recording_manager: RecordingManager):
        if not isinstance(recording_manager, RecordingManager):
            raise ValueError(f"Expected RecordingManager, got {type(recording_manager)} in recording_manager")
        ipc.video_manager_status.is_recording_frames_flag.value = False
        while not recording_manager.is_finished:
            logger.debug(f"Finishing RecordingManager `{recording_manager.recording_info.recording_name}`...")
            ipc.video_manager_status.finishing.value = True
            recording_manager.finish_and_close()
            ipc.video_manager_status.finishing.value = False

        return recording_manager
