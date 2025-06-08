import logging
from abc import ABC
from multiprocessing.process import parent_process
from typing import Type

from pydantic import BaseModel, Field, ConfigDict

from skellycam.core.types import TopicSubscriptionQueue, TopicPublicationQueue

logger = logging.getLogger(__name__)

class TopicMessageABC(BaseModel, ABC):
    """
    Base class for messages sent through the PubSub system.
    All messages should inherit from this class.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)


class PubSubTopicABC(BaseModel, ABC):
    subscriptions: list[TopicSubscriptionQueue] = Field(default_factory=list)
    message_type: Type[TopicMessageABC] = Field(default_factory=TopicMessageABC)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


    def get_subscription(self) -> TopicSubscriptionQueue:
        """
        Subscribe a queue to this topic.
        """
        if parent_process() is not None:
            raise RuntimeError("Subscriptions must be created in the main process and passed to children")
        sub = TopicSubscriptionQueue()
        self.subscriptions.append(sub)
        return sub


    def publish(self, message:TopicMessageABC):
        """
        Publish a message to all subscribers of this topic.
        """
        if not isinstance(message, self.message_type):
            raise TypeError(f"Expected {self.message_type} but got {type(message)}")
        logger.trace(f"Publishing message of type {self.message_type} to {len(self.subscriptions)} subscribers")
        for sub in self.subscriptions:
            sub.put(message)

