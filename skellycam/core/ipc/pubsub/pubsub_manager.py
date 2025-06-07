import logging
import multiprocessing
from enum import Enum, auto
from multiprocessing.process import parent_process

from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.ipc.pubsub.pubsub_abcs import TopicMessageABC, PubSubTopicABC
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateConfigsTopic, ShmUpdatesTopic, RecordingInfoTopic, \
    ExtractedConfigTopic
from skellycam.core.types import CameraGroupIdString, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


class TopicTypes(Enum):
    UPDATE_CONFIGS = auto()
    EXTRACTED_CONFIG = auto()
    SHM_UPDATES = auto()
    RECORDING_INFO = auto()


class PubSubTopicManager(BaseModel):
    topics: dict[TopicTypes, PubSubTopicABC] = Field(default_factory=lambda: {
        TopicTypes.UPDATE_CONFIGS: UpdateConfigsTopic(),
        TopicTypes.EXTRACTED_CONFIG: ExtractedConfigTopic(),
        TopicTypes.SHM_UPDATES: ShmUpdatesTopic(),
        TopicTypes.RECORDING_INFO: RecordingInfoTopic(),
    })
    should_continue_flag: multiprocessing.Value = Field(default_factory=lambda: multiprocessing.Value('b', False))
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def get_subscription(self, topic_type: TopicTypes) -> TopicSubscriptionQueue:
        """
        Get a subscription queue for a specific topic type.
        Raises an error if the topic type is not recognized.
        """
        if parent_process() is not None:
            raise RuntimeError("Subscriptions must be created in the main process and passed to children")

        if topic_type not in self.topics:
            raise ValueError(f"Unknown topic type: {topic_type}")
        sub= self.topics[topic_type].get_subscription()
        logger.trace(f"Subscribed to topic {topic_type.name} with {len(self.topics[topic_type].subscriptions)} subscriptions")
        return sub




PUB_SUB_MANAGERS: dict[CameraGroupIdString, PubSubTopicManager] = {}


def create_pubsub_manager(group_id: CameraGroupIdString) -> PubSubTopicManager:
    """
    Create a global PubSubManager instance, raises an error if called in a non-main process.
    """
    global PUB_SUB_MANAGERS
    if parent_process() is not None:
        raise RuntimeError("PubSubManager can only be created in the main process.")
    if PUB_SUB_MANAGERS.get(group_id) is not None:
        raise ValueError(f"PubSubManager for group {group_id} already exists.")
    PUB_SUB_MANAGERS[group_id] = PubSubTopicManager()
    return PUB_SUB_MANAGERS[group_id]


