from typing import List

from fast_camera_capture.multiproc.queue import Queue


class QueueCommunicator:
    def __init__(self, identifiers: List[str]):
        self._identifiers = identifiers
        self._queues = self._create_queues()

    def _create_queues(self):
        d = {}
        for identifier in self._identifiers:
            d.update({
                identifier: Queue()
            })
        return d

    @property
    def queues(self):
        return self._queues


