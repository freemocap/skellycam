import multiprocessing
from typing import List

from skellycam.detection.models.frame_payload import FramePayload


class SharedCameraMemoryManager:
    def __init__(self):
        self._mr_manager = multiprocessing.Manager()

    def create_frame_lists_by_camera(self, keys: List[str]):
        dictionary = self._mr_manager.dict()

        for key in keys:
            list = self._mr_manager.list()
            list.append(FramePayload())
            dictionary.update({key: list})

        return dictionary

    def create_video_save_path_dictionary(self, keys: List[str]):
        dictionary = self._mr_manager.dict()

        for key in keys:
            dictionary.update({key: self._mr_manager.Value('s', '')})
        return dictionary

    def create_camera_config_dictionary(self, keys: List[str]):
        dictionary = self._mr_manager.dict()
        for key in keys:
            dictionary.update({key: None})
        return dictionary

    def create_video_save_folder_list(self):
        return self._mr_manager.list()

    def create_value(self, type: str, initial_value=None):
        return self._mr_manager.Value(type, initial_value)
