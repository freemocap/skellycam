import multiprocessing
from typing import List, Dict

from skellycam import CameraConfig
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

    def create_camera_config_dictionary(self, keys: List[str]) -> Dict[str, List[CameraConfig]]:
        dictionary = self._mr_manager.dict()
        for key in keys:
            dictionary.update({key: self._mr_manager.list()})
        return dictionary

    def create_video_save_folder_list(self):
        return self._mr_manager.list()

    def create_value(self, type: str, initial_value=None):
        return self._mr_manager.Value(type, initial_value)

    def create_camera_config_queues(self, camera_ids:List[str]):
        camera_config_queues = self._mr_manager.dict()
        for camera_id in camera_ids:
            queue = self._mr_manager.Queue()
            queue.put(CameraConfig(camera_id=camera_id))
            camera_config_queues.update({camera_id: queue})
        return camera_config_queues
