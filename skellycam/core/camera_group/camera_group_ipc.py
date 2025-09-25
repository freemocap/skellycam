import logging
import multiprocessing

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.ipc.pubsub.pubsub_manager import create_camera_group_pubsub_manager, TopicTypes, PubSubTopicManager
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage
from skellycam.core.types.type_overloads import CameraGroupIdString, TopicSubscriptionQueue
from skellycam.utilities.create_camera_group_id import create_camera_group_id

logger = logging.getLogger(__name__)


class CameraGroupIPC(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )
    group_id: CameraGroupIdString
    pubsub: PubSubTopicManager
    timebase_mapping: TimebaseMapping = Field(default_factory=TimebaseMapping)
    extracted_config_subscription: TopicSubscriptionQueue
    recording_finished_subscription: TopicSubscriptionQueue

    should_pause: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))
    shutdown_camera_group_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value("b", False))


    global_kill_flag: SkipValidation[multiprocessing.Value]

    @classmethod
    def create(cls,
               global_kill_flag: multiprocessing.Value,
               group_id: CameraGroupIdString | None = None) -> 'CameraGroupIPC':

        if group_id is None:
            group_id = create_camera_group_id()
        pubsub = create_camera_group_pubsub_manager(group_id=group_id)

        return cls(
            group_id=group_id,
            pubsub=pubsub,
            extracted_config_subscription=pubsub.topics[TopicTypes.EXTRACTED_CONFIG].get_subscription(),
            recording_finished_subscription=pubsub.topics[TopicTypes.RECORDING_FINISHED].get_subscription(),
            global_kill_flag=global_kill_flag,

        )

    @property
    def should_continue(self) -> bool:
        return not self.shutdown_camera_group_flag.value and not self.global_kill_flag.value

    @should_continue.setter
    def should_continue(self, value: bool) -> None:
        logger.api(f"Setting should_continue to {value} for camera group {self.group_id}")
        self.shutdown_camera_group_flag.value = not value

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

