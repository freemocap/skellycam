import logging
import multiprocessing
from abc import ABC
from dataclasses import dataclass, field
from multiprocessing.process import parent_process
from typing import Type

from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_100ms

logger = logging.getLogger(__name__)

@dataclass
class TopicMessageABC(ABC):
    """
    Base class for messages sent through the PubSub system.
    All messages should inherit from this class.
    """
    pass


@dataclass
class PubSubTopicABC(ABC):
    subscriptions: list[TopicSubscriptionQueue] = field(default_factory=list)
    message_type: Type[TopicMessageABC] = TopicMessageABC


    def get_subscription(self) -> TopicSubscriptionQueue:
        """
        Subscribe a queue to this topic.
        """
        if parent_process() is not None:
            raise RuntimeError("Subscriptions must be created in the main process and passed to children")
        sub =  multiprocessing.Queue()
        self.subscriptions.append(sub)
        return sub


    def publish(self, message:TopicMessageABC, overwrite:bool=False, print_log:bool=True):
        """
        Publish a message to all subscribers of this topic.
        """
        if not isinstance(message, self.message_type):
            raise TypeError(f"Expected {self.message_type} but got {type(message)}")
        if len(self.subscriptions) == 0:
            logger.warning(f"Publishing message of type {self.message_type} with no subscribers, message will be lost")
            return
        if print_log:
            logger.trace(f"Publishing message of type {self.message_type} to {len(self.subscriptions)} subscribers")
        for sub in self.subscriptions:
            if overwrite:
                overwrote = 0
                while not sub.empty():
                    sub.get()
                    overwrote += 1
                if overwrote > 0 and print_log:
                    logger.trace(f"Overwrote {overwrote} messages in subscription queue {sub}")
            sub.put(message)
    def close(self):
        """
        Close all subscriptions for this topic.

        cancel_join_thread() is required alongside close(): multiprocessing.Queue
        registers an untimed atexit finalizer that joins its feeder thread on
        interpreter shutdown. If the process on the other end of the pipe already
        exited, that feeder thread can be stuck retrying a write and the join
        hangs forever -- causing a process to print its final output but never
        exit.

        Note this doesn't wait for a queued message's flush to finish before
        returning, only for the wait_100ms() below to elapse -- so a message
        put() immediately before close() could in principle still be in flight
        and get dropped rather than delivered. In practice that window is the
        same one wait_100ms() already existed to paper over; we're not making
        it wider, just no longer blocking indefinitely if the feeder thread
        happens to be stuck rather than merely slow.
        """
        logger.debug(f"Closing PubSubTopicABC {self.__class__.__name__} with {len(self.subscriptions)} subscriptions")
        for sub in self.subscriptions:
            sub.close()
            sub.cancel_join_thread()
        wait_100ms()
        self.subscriptions.clear()
        logger.debug(f"Closed PubSubTopicABC {self.__class__.__name__}")
