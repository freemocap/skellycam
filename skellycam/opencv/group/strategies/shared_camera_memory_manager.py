import multiprocessing
from typing import List

from skellycam.detection.models.frame_payload import FramePayload


class SharedCameraMemoryManager:
    def __init__(self):
        self._mr_manager = multiprocessing.Manager()


    def create_dictionary_of_lists(self, keys: List[str]):
        dictionary = self._mr_manager.dict()

        for key in keys:
            dictionary.update({key: self._mr_manager.list()})

        return dictionary

    def create_dictionary_of_strings(self, keys: List[str]):
        dictionary = self._mr_manager.dict()

        for key in keys:
            dictionary.update({key: self._mr_manager.Value('s', '')})
        return dictionary

    def create_dictionary(self, keys: List[str]):
        dictionary = self._mr_manager.dict()
        for key in keys:
            dictionary.update({key: None})
        return dictionary

    def create_value(self, type: str, initial_value=None):
        return self._mr_manager.Value(type, initial_value)
