import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.ipc.pubsub.pubsub_manager import create_pubsub_manager, TopicTypes, PubSubTopicManager
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.recorders.mf_builder_status import MultiFrameBuilderStatus
from skellycam.core.recorders.recording_manager_status import RecordingManagerStatus
from skellycam.core.types.type_overloads import CameraGroupIdString, TopicSubscriptionQueue
from skellycam.utilities.create_camera_group_id import create_camera_group_id
from skellycam.utilities.wait_functions import wait_100ms

logger = logging.getLogger(__name__)


class CameraGroupIPC(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    group_id: CameraGroupIdString
    pubsub: PubSubTopicManager
    timebase_mapping: TimebaseMapping = Field(default_factory=TimebaseMapping)
    camera_orchestrator: CameraOrchestrator
    extracted_config_subscription: TopicSubscriptionQueue

    recording_manager_status: RecordingManagerStatus = Field(default_factory=RecordingManagerStatus)
    mf_builder_status: MultiFrameBuilderStatus = Field(default_factory=MultiFrameBuilderStatus)
    shutdown_camera_group_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))

    global_kill_flag: SkipValidation[multiprocessing.Value]

    @classmethod
    def create(cls, camera_configs: CameraConfigs, global_kill_flag: multiprocessing.Value,
               group_id: CameraGroupIdString | None = None) -> 'CameraGroupIPC':
        validate_camera_configs(camera_configs)
        if group_id is None:
            group_id = create_camera_group_id()
        pubsub = create_pubsub_manager(group_id=group_id)
        return cls(
            group_id=group_id,
            pubsub=pubsub,
            camera_orchestrator=CameraOrchestrator.from_camera_ids(camera_ids=list(camera_configs.keys())),
            extracted_config_subscription=pubsub.topics[TopicTypes.EXTRACTED_CONFIG].get_subscription(),
            global_kill_flag=global_kill_flag,

        )

    @property
    def should_continue(self) -> bool:
        return not self.shutdown_camera_group_flag.value and not self.global_kill_flag.value

    @should_continue.setter
    def should_continue(self, value: bool) -> None:
        self.shutdown_camera_group_flag.value = not value

    @property
    def all_ready(self) -> bool:
        """
        Check if all cameras in the group are ready.
        """
        return self.camera_orchestrator.all_cameras_ready and self.recording_manager_status.is_running_flag.value
    @property
    def all_paused(self) -> bool:
        return all([
            self.camera_orchestrator.all_cameras_paused,
            self.recording_manager_status.is_paused.value,
            self.mf_builder_status.is_paused.value
        ])

    @property
    def all_unpaused(self) -> bool:
        return not any([
            self.camera_orchestrator.all_cameras_paused,
            self.recording_manager_status.is_paused.value,
            self.mf_builder_status.is_paused.value
        ])
    def publish_shm_message(self, shm_dto) -> None:
        """
        Publish a shared memory message to the pubsub system.
        """
        shm_update_message = SetShmMessage(
            camera_group_shm_dto=shm_dto,
        )
        self.pubsub.topics[TopicTypes.SHM_UPDATES].publish(shm_update_message)

    def kill_everything(self) -> None:
        self.global_kill_flag.value = True

    def pause(self, await_paused: bool = True) -> None:
        """
        Pause the camera group.
        """
        self.mf_builder_status.should_pause.value = True
        self.recording_manager_status.should_pause.value = True
        self.camera_orchestrator.pause(await_paused)
        if await_paused:
            while not self.all_paused:
                wait_100ms()

    def unpause(self, await_unpaused: bool = True) -> None:
        """
        Unpause the camera group.
        """
        self.mf_builder_status.should_pause.value = False
        self.recording_manager_status.should_pause.value = False
        self.camera_orchestrator.unpause(await_unpaused)
        if await_unpaused:
            while not self.all_unpaused:
                wait_100ms()