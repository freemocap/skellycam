import logging
import multiprocessing

import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage, RecordingInfoMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryManager
from skellycam.core.recorders.audio.audio_recorder import AudioRecorder
from skellycam.core.recorders.recording_manager_status import RecordingManagerStatus
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_manager import VideoManager
from skellycam.core.types.type_overloads import TopicSubscriptionQueue, CameraIdString, WorkerType, WorkerStrategy
from skellycam.utilities.wait_functions import wait_10ms, wait_1ms

logger = logging.getLogger(__name__)


class RecordingManager(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    worker: WorkerType
    ipc: CameraGroupIPC

    @property
    def status(self):
        return self.ipc.recording_manager_status

    @classmethod
    def create(cls,
               ipc: CameraGroupIPC,
               worker_strategy: WorkerStrategy):
        return cls(
            ipc=ipc,
            worker=worker_strategy.value(target=cls._run_recording_manager,
                                         name='RecordingManagerWorker',
                                         kwargs=dict(ipc=ipc,
                                                     recording_info_subscription=ipc.pubsub.topics[
                                                         TopicTypes.RECORDING_INFO].get_subscription(),
                                                     shm_updates_subscription=ipc.pubsub.topics[
                                                         TopicTypes.SHM_UPDATES].get_subscription(),

                                                     ),
                                         daemon=True),
        )

    @property
    def ready(self):
        return self.worker.is_alive()

    def start(self):
        logger.debug(f"Starting video worker process...")
        self.worker.start()

    def is_alive(self) -> bool:
        return self.worker.is_alive()



    @staticmethod
    def _run_recording_manager(ipc: CameraGroupIPC,
                               recording_info_subscription: TopicSubscriptionQueue,
                               shm_updates_subscription: TopicSubscriptionQueue,
                               ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from skellycam.system.logging_configuration.configure_logging import configure_logging
            from skellycam import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)


        status: RecordingManagerStatus = ipc.recording_manager_status
        camera_group_shm: CameraGroupSharedMemoryManager | None = None

        while ipc.should_continue  and camera_group_shm is None:

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
            else:
                # wait for the shared memory to be created
                wait_10ms()

        # Ensure camera_group_shm is properly initialized before proceeding
        if camera_group_shm is None or not camera_group_shm.valid:
            raise RuntimeError("Failed to initialize camera_group_shm")



        video_manager: VideoManager | None = None
        camera_config_recarrays: dict[CameraIdString, np.recarray]| None = None
        audio_recorder: AudioRecorder | None = None
        status.is_running_flag.value = True
        logger.success(f"VideoManager process started for camera group `{ipc.group_id}`")
        try:
            while ipc.should_continue :
                wait_1ms()
                # check for new recording info
                if status.should_record.value and video_manager is None:
                    recording_info_message = recording_info_subscription.get(block=True)
                    if not isinstance(recording_info_message, RecordingInfoMessage):
                        raise RuntimeError(
                            f"Expected RecordingInfo, got {type(recording_info_message)} in recording_info_subscription"
                        )

                    video_manager = RecordingManager.start_recording(status=status,
                                                                     recording_info=recording_info_message.recording_info,
                                                                     camera_config_recarrays=camera_config_recarrays,
                                                                     video_manager=video_manager)


                # check for shared memory updates
                if not shm_updates_subscription.empty():
                    raise NotImplementedError("Runtime updates of shared memory are not yet implemented.")

                # check/handle new multi-frames
                video_manager, camera_config_recarrays = RecordingManager._get_and_handle_new_mfs(
                    status=status,
                    video_manager=video_manager,
                    camera_group_shm=camera_group_shm,
                    camera_config_recarrays=camera_config_recarrays
                )

        except Exception as e:
            status.error.value = True
            ipc.kill_everything()
            logger.error(f"RecordingManager process error: {e}")
            logger.exception(e)
            raise

        except KeyboardInterrupt:
            pass
        finally:
            status.is_running_flag.value = False
            ipc.should_continue = False
            if video_manager:
                video_manager.finish_and_close()
            if camera_group_shm:
                camera_group_shm.close()
                logger.trace("Camera group shared memory closed in RecordingManager worker.")
            logger.debug("RecordingManager worker completed")

    @staticmethod
    def _get_and_handle_new_mfs(status: RecordingManagerStatus,
                                camera_group_shm: CameraGroupSharedMemoryManager,
                                video_manager: VideoManager | None,
                                camera_config_recarrays: dict[CameraIdString, np.recarray] | None,
                                ) ->tuple[VideoManager | None, CameraConfigs | None]:

        latest_mf_recarrays = camera_group_shm.multi_frame_ring_shm.get_all_new_multiframes()

        if len(latest_mf_recarrays) > 0:
            # if new frames, add them to the recording manager (doesn't save them yet)
            current_configs = {camera_id:latest_mf_recarrays[0][camera_id].frame_metadata.camera_config[0]
                                 for camera_id in latest_mf_recarrays[0].dtype.names}

            if video_manager is not None:
                if camera_config_recarrays != current_configs:
                    raise ValueError('Cannot change camera configs while recording is active!')
                video_manager.add_multi_frame_recarrays(latest_mf_recarrays)
            camera_config_recarrays = current_configs
        else:
            if video_manager:
                if status.should_record.value:
                    # if we're recording and there are no new frames, opportunistically save one frame if we're recording
                    video_manager.save_one_frame()
                else:
                    # if we have a video manager but not recording, then finish and close it
                    video_manager = RecordingManager.stop_recording(status=status, video_manager=video_manager)

        return video_manager, camera_config_recarrays

    @staticmethod
    def start_recording(status: RecordingManagerStatus,
                        recording_info: RecordingInfo,
                        camera_config_recarrays: dict[CameraIdString, np.recarray],
                        video_manager: VideoManager | None) -> VideoManager | None:
        camera_configs = {camera_id: CameraConfig.from_numpy_record_array(camera_config_recarrays[camera_id])
                                   for camera_id in camera_config_recarrays.keys()}
        if isinstance(video_manager, VideoManager):
            RecordingManager.stop_recording(status=status, video_manager=video_manager)


        if not isinstance(camera_configs, dict) or any(
                [not isinstance(config, CameraConfig) for config in camera_configs.values()]):
            raise ValueError(f"Expected CameraConfigs, got {type(camera_configs)} in camera_configs")

        logger.info(f"Creating RecodingManager for recording: `{recording_info.recording_name}`")
        status.updating.value = True
        video_manager = VideoManager.create(recording_info=recording_info,
                                            camera_configs=camera_configs,
                                            )
        status.updating.value = False
        status.is_recording_frames_flag.value = True
        return video_manager

    @staticmethod
    def stop_recording(status: RecordingManagerStatus, video_manager: VideoManager) -> None:
        logger.info(f"Stopping recording: `{video_manager.recording_info.recording_name}`...")
        status.is_recording_frames_flag.value = False

        status.finishing.value = True
        video_manager.finish_and_close()
        status.finishing.value = False

        return None
