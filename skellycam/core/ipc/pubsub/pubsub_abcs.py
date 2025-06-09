import logging
from abc import ABC
from multiprocessing.process import parent_process
from typing import Type

import numpy as np
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


    def publish(self, message:TopicMessageABC, overwrite:bool=False):
        """
        Publish a message to all subscribers of this topic.
        """
        if not isinstance(message, self.message_type):
            raise TypeError(f"Expected {self.message_type} but got {type(message)}")
        logger.trace(f"Publishing message of type {self.message_type} and size {len(message.model_dump_json())/1024:.2f}KB to {len(self.subscriptions)} subscribers with ~{np.mean([sub.qsize() for sub in self.subscriptions]):.2f} messages per subscriber")
        for sub in self.subscriptions:
            if overwrite:
                overwrote = 0
                while not sub.empty():
                    sub.get()
                    overwrote += 1
                logger.trace(f"Overwrote {overwrote} messages in subscription queue {sub}")
            sub.put(message)

