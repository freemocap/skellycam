import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.camera_group.status_models import RecordingManagerStatus
from skellycam.core.ipc.pubsub.pubsub_manager import create_pubsub_manager, TopicTypes, PubSubTopicManager
from skellycam.core.types import CameraGroupIdString, TopicSubscriptionQueue
from skellycam.utilities.create_camera_group_id import create_camera_group_id

logger = logging.getLogger(__name__)


class CameraGroupIPC(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    group_id: CameraGroupIdString
    pubsub: PubSubTopicManager

    extracted_configs_subscription_queue: TopicSubscriptionQueue
    recording_manager_status: RecordingManagerStatus = Field(default_factory=RecordingManagerStatus)

    lock: SkipValidation[multiprocessing.Lock] = Field(default_factory=multiprocessing.Lock)
    shutdown_camera_group_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    updating_cameras_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    should_pause_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    main_process_backpressure: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("i", 0))

    global_kill_flag: SkipValidation[multiprocessing.Value]

    @classmethod
    def create(cls, camera_configs: CameraConfigs, global_kill_flag: multiprocessing.Value) -> 'CameraGroupIPC':
        validate_camera_configs(camera_configs)
        group_id = create_camera_group_id()
        pubsub = create_pubsub_manager(group_id=group_id)
        return cls(
            group_id=group_id,
            pubsub=pubsub,
            extracted_configs_subscription_queue=pubsub.topics[TopicTypes.EXTRACTED_CONFIG].get_subscription(),
            global_kill_flag=global_kill_flag,

        )

    @property
    def should_continue(self) -> bool:
        return not self.shutdown_camera_group_flag.value and not self.global_kill_flag.value

    @should_continue.setter
    def should_continue(self, value: bool) -> None:
        self.shutdown_camera_group_flag.value = not value



    @property
    def recording_manager_ready(self) -> bool:
        return self.recording_manager_status.is_running_flag.value
    # @property
    # def all_ready(self) -> bool:
        # return self.camera_orchestrator.all_cameras_ready and self.recording_manager_status.is_running_flag.value

    # @property
    # def all_paused(self) -> bool:
    #     return all([not self.camera_orchestrator.all_cameras_paused,
    #                 not self.recording_manager_status.is_paused_flag.value])
    #
    # @property
    # def any_paused(self) -> bool:
    #     return any([not self.camera_orchestrator.any_cameras_paused,
    #                 not self.recording_manager_status.is_paused_flag.value])
    #
    # @property
    # def running(self) -> bool:
    #     return not self.shutdown_camera_group_flag.value
    #
    # def start_recording(self, recording_info: RecordingInfo) -> None:
    #     if self.any_recording:
    #         raise ValueError("Cannot start recording while recording is in progress.")
    #     self.pubsub.topics[TopicTypes.RECORDING_INFO].publish(RecordingInfoMessage(recording_info=recording_info))
    #     self.recording_manager_status.should_record.value = True
    #
    # def stop_recording(self) -> None:
    #     if not self.all_recording:
    #         raise ValueError("Cannot stop recording - no recording is in progress.")
    #     logger.info("Sending `stop recording` signal")
    #     self.recording_manager_status.should_record.value = False
    #     while self.recording_manager_status.is_recording_frames_flag.value:
    #         wait_30ms()
    #
    # def close_camera_group(self) -> None:
    #     if self.recording_manager_status.is_recording_frames_flag.value:
    #         self.stop_recording()
    #     self.shutdown_camera_group_flag.value = True
    #
    # def pause(self, await_paused: bool = False) -> None:
    #     """
    #     Pause the camera group IPC.
    #     If await_paused is True, it will block until the pause is acknowledged.
    #     """
    #     self.should_pause_flag.value = True
    #     if await_paused:
    #         while not self.all_paused and self.should_continue:
    #             wait_10ms()
    #     logger.info("Camera group IPC paused.")
    #
    # def unpause(self, await_unpaused: bool = False) -> None:
    #     self.should_pause_flag.value = False
    #     if await_unpaused:
    #         while self.any_paused and self.should_continue:
    #             wait_10ms()
    #     logger.info("Camera group IPC unpaused.")

    def kill_everything(self) -> None:
        self.global_kill_flag.value = True