import logging
from abc import ABC
from multiprocessing.process import parent_process
from typing import Type

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from skellycam.core.types import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_100ms

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
        if len(self.subscriptions) == 0:
            logger.warning(f"Publishing message of type {self.message_type} with no subscribers, message will be lost")
            return
        logger.trace(f"Publishing message of type {self.message_type} to {len(self.subscriptions)} subscribers with ~{np.mean([sub.qsize() for sub in self.subscriptions]):.2f} messages per subscriber")
        for sub in self.subscriptions:
            if overwrite:
                overwrote = 0
                while not sub.empty():
                    sub.get()
                    overwrote += 1
                logger.trace(f"Overwrote {overwrote} messages in subscription queue {sub}")
            sub.put(message)
    def close(self):
        """
        Close all subscriptions for this topic.
        """
        logger.debug(f"Closing PubSubTopicABC {self.__class__.__name__} with {len(self.subscriptions)} subscriptions")
        for sub in self.subscriptions:
            sub.close()
        wait_100ms()
        self.subscriptions.clear()
        logger.debug(f"Closed PubSubTopicABC {self.__class__.__name__}")
