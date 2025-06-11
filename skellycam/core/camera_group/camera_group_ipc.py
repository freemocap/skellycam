import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs, CameraConfig, \
    ThreadSafeCameraConfigs
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.status_models import VideoManagerStatus, MutliFramePublisherStatus
from skellycam.core.ipc.pubsub.pubsub_manager import create_pubsub_manager, TopicTypes, PubSubTopicManager
from skellycam.core.ipc.pubsub.pubsub_topics import RecordingInfoMessage
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraIdString, CameraGroupIdString, TopicSubscriptionQueue
from skellycam.utilities.create_camera_group_id import create_camera_group_id
from skellycam.utilities.wait_functions import wait_10ms, wait_30ms

logger = logging.getLogger(__name__)


class CameraGroupIPC(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    group_id: CameraGroupIdString
    pubsub: PubSubTopicManager
    ipc_camera_configs: CameraConfigs

    camera_orchestrator: CameraOrchestrator
    extracted_configs_subscription_queue: TopicSubscriptionQueue
    video_manager_status: VideoManagerStatus = Field(default_factory=VideoManagerStatus)
    mf_publisher_status: MutliFramePublisherStatus = Field(default_factory=MutliFramePublisherStatus)

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
            ipc_camera_configs=camera_configs,
            camera_orchestrator=CameraOrchestrator.from_camera_ids(camera_ids=list(camera_configs.keys())),
            extracted_configs_subscription_queue=pubsub.topics[TopicTypes.EXTRACTED_CONFIG].get_subscription(),
            global_kill_flag=global_kill_flag,
        )



    @property
    def camera_configs(self) -> CameraConfigs:
        return self.ipc_camera_configs



    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())

    @property
    def should_continue(self) -> bool:
        return not self.shutdown_camera_group_flag.value and not self.global_kill_flag.value

    @should_continue.setter
    def should_continue(self, value: bool) -> None:
        self.shutdown_camera_group_flag.value = not value


    @property
    def any_recording(self) -> bool:
        return self.video_manager_status.is_recording_frames_flag.value or self.video_manager_status.should_record.value

    @property
    def all_recording(self) -> bool:
        return self.video_manager_status.is_recording_frames_flag.value and self.video_manager_status.should_record.value

    @property
    def all_ready(self) -> bool:
        return self.camera_orchestrator.all_cameras_ready and self.video_manager_status.is_running_flag.value and self.mf_publisher_status.is_running_flag.value

    @property
    def all_paused(self) -> bool:
        return all([not self.camera_orchestrator.all_cameras_paused,
                    not self.video_manager_status.is_paused_flag.value,
                    not self.mf_publisher_status.is_paused_flag.value])

    @property
    def any_paused(self) -> bool:
        return any([not self.camera_orchestrator.any_cameras_paused,
                    not self.video_manager_status.is_paused_flag.value,
                    not self.mf_publisher_status.is_paused_flag.value])

    @property
    def running(self) -> bool:
        return not self.shutdown_camera_group_flag.value

    def add_camera(self, config: CameraConfig) -> None:
        self.camera_configs[config.camera_id] = config
        self.camera_orchestrator.add_camera(config)

    def remove_camera(self, camera_id: CameraIdString) -> None:
        self.camera_configs.pop(camera_id)
        self.camera_orchestrator.remove_camera(camera_id)


    def start_recording(self, recording_info: RecordingInfo) -> None:
        if self.any_recording:
            raise ValueError("Cannot start recording while recording is in progress.")
        self.pubsub.topics[TopicTypes.RECORDING_INFO].publish(RecordingInfoMessage(recording_info=recording_info))
        self.video_manager_status.should_record.value = True

    def stop_recording(self) -> None:
        if not self.all_recording:
            raise ValueError("Cannot stop recording - no recording is in progress.")
        logger.info("Sending `stop recording` signal")
        self.video_manager_status.should_record.value = False
        while self.video_manager_status.is_recording_frames_flag.value:
            wait_30ms()

    def close_camera_group(self) -> None:
        if self.video_manager_status.is_recording_frames_flag.value:
            self.stop_recording()
        self.shutdown_camera_group_flag.value = True

    def pause(self, await_paused: bool = False) -> None:
        """
        Pause the camera group IPC.
        If await_paused is True, it will block until the pause is acknowledged.
        """
        self.should_pause_flag.value = True
        if await_paused:
            while not self.all_paused and self.should_continue:
                wait_10ms()
        logger.info("Camera group IPC paused.")

    def unpause(self, await_unpaused: bool = False) -> None:
        self.should_pause_flag.value = False
        if await_unpaused:
            while self.any_paused and self.should_continue:
                wait_10ms()
        logger.info("Camera group IPC unpaused.")

    def kill_everything(self) -> None:
        self.global_kill_flag.value = True