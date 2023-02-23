import multiprocessing
from copy import deepcopy
from typing import List, Any


class SharedCameraMemoryManager:
    def __init__(self):
        self._mr_manager = multiprocessing.Manager()

    def create_dictionary(self, keys: List[str], initial_value: Any = None):
        dictionary = self._mr_manager.dict()

        for key in keys:
            dictionary.update({key: deepcopy(initial_value)})

        return dictionary

    def create_value(self, type: str, initial_value=None):
        return self._mr_manager.Value(type, initial_value)
