import multiprocessing
from typing import List


class QueueCommunicator:
    def __init__(self, identifiers: List[str]):
        self._identifiers = identifiers
        self._mr_manager = multiprocessing.Manager()
        self._queues = self._create_queues()
        self._shared_dictionary = self._create_shared_dictionary()

    def _create_queues(self):
        d = {}
        for identifier in self._identifiers:
            d.update({identifier: self._mr_manager.Queue()})
        return d

    @property
    def queues(self):
        return self._queues

    @property
    def shared_dictionary(self):
        return self._shared_dictionary

    def _create_shared_dictionary(self):
        shared_dictionary = self._mr_manager.dict()
        for identifier in self._identifiers:
            shared_dictionary[identifier] = None
        return shared_dictionary
