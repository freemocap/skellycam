import logging
import multiprocessing
from enum import Enum, auto
from multiprocessing.process import parent_process

from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from skellycam.core.ipc.pubsub.pubsub_abcs import PubSubTopicABC
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateCameraSettingsTopic, ShmUpdatesTopic, RecordingInfoTopic, \
    ExtractedConfigTopic, FrontendPayloadTopic, LogsTopic, NewConfigsTopic
from skellycam.core.types import CameraGroupIdString, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


class TopicTypes(Enum):
    UPDATE_CAMERA_SETTINGS = auto() #User requested updates to camera configs (i.e. the desired camera settings)
    EXTRACTED_CONFIG = auto() #Camera Configs extracted from the camera (i.e. the actual camera settings)
    NEW_CONFIGS = auto() #New camera configs (to inform Nodes when there are new configs available, based on the extracted configs)
    SHM_UPDATES = auto()
    RECORDING_INFO = auto()
    FRONTEND_PAYLOAD = auto()
    LOGS = auto()


class PubSubTopicManager(BaseModel):
    topics: dict[TopicTypes, PubSubTopicABC] = Field(default_factory=lambda: {
        TopicTypes.UPDATE_CAMERA_SETTINGS: UpdateCameraSettingsTopic(),
        TopicTypes.EXTRACTED_CONFIG: ExtractedConfigTopic(),
        TopicTypes.NEW_CONFIGS: NewConfigsTopic(),
        TopicTypes.SHM_UPDATES: ShmUpdatesTopic(),
        TopicTypes.RECORDING_INFO: RecordingInfoTopic(),
        TopicTypes.FRONTEND_PAYLOAD: FrontendPayloadTopic(),
        TopicTypes.LOGS: LogsTopic(),
    })
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


