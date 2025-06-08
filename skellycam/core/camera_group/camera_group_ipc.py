import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager, create_pubsub_manager, TopicTypes
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraIdString, CameraGroupIdString, TopicSubscriptionQueue
from skellycam.utilities.create_camera_group_id import create_camera_group_id
from skellycam.utilities.wait_functions import wait_10ms, wait_30ms

logger = logging.getLogger(__name__)



class VideoManagerStatus(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    is_recording_frames_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    should_record: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    is_running_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    finishing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    is_paused_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))

    @property
    def recording(self) -> bool:
        return self.is_recording_frames_flag.value and self.should_record.value


class MutliFramePublisherStatus(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    is_running_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    is_paused_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    total_frames_published: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('Q', 0))
    number_frames_published_this_cycle: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('i', 0))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))


class CameraGroupIPC(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    group_id: CameraGroupIdString
    pubsub: PubSubTopicManager
    camera_orchestrator: CameraOrchestrator
    extracted_configs_subscription_queue: TopicSubscriptionQueue
    video_manager_status: VideoManagerStatus = Field(default_factory=VideoManagerStatus)
    mf_publisher_status: MutliFramePublisherStatus = Field(default_factory=MutliFramePublisherStatus)

    shutdown_camera_group_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    updating_cameras_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))
    should_pause_flag: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value("b", False))

    @classmethod
    def create(cls, camera_configs: CameraConfigs):
        validate_camera_configs(camera_configs)
        group_id = create_camera_group_id()
        pubsub  = create_pubsub_manager(group_id=group_id)
        return cls(
            group_id=group_id,
            pubsub=pubsub,
            extracted_configs_subscription_queue = pubsub.topics[TopicTypes.EXTRACTED_CONFIG].get_subscription(),
            camera_orchestrator=CameraOrchestrator.from_configs(camera_configs=camera_configs)
        )

    @property
    def camera_connections(self):
        return self.camera_orchestrator.connections

    @property
    def camera_configs(self) -> CameraConfigs:
        return {connection.config.camera_id: connection.config for connection in self.camera_connections.values()}

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.camera_configs.keys())

    @property
    def should_continue(self) -> bool:
        return not self.shutdown_camera_group_flag.value

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
    def start_recording(self, recording_info: RecordingInfo) -> None:
        if self.any_recording:
            raise ValueError("Cannot start recording while recording is in progress.")
        self.pubsub.topics[TopicTypes.RECORDING_INFO].publish(recording_info)
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
