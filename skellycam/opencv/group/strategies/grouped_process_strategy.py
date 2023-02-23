import logging
import multiprocessing
from typing import Dict, List, Union

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.cam_group_process import CamGroupProcess
from skellycam.opencv.group.strategies.shared_camera_memory_manager import SharedCameraMemoryManager
from skellycam.utils.array_split_by import array_split_by

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

logger = logging.getLogger(__name__)


class GroupedProcessStrategy:
    def __init__(self, camera_ids: List[str]):
        self._camera_ids = camera_ids

        shared_memory_manager = SharedCameraMemoryManager()
        self._latest_frames = shared_memory_manager.create_dictionary(keys=self._camera_ids)
        self._frame_dictionaries = shared_memory_manager.create_dictionary(keys=self._camera_ids, initial_value={})
        self._incoming_camera_configs = shared_memory_manager.create_dictionary(keys=self._camera_ids,
                                                                                initial_value=CameraConfig())
        self._recording_frames = shared_memory_manager.create_value(type='b', initial_value=False)

        self._processes, self._cam_id_process_map = self._create_processes(self._camera_ids)

    @property
    def processes(self):
        return self._processes

    @property
    def is_capturing(self):
        for process in self._processes:
            if not process.is_capturing:
                return False
        return True

    @property
    def frame_dictionaries(self) -> Dict[str, Dict[str, Union[str, List[FramePayload]]]]:
        return self._frame_dictionaries

    @property
    def frame_list_lengths(self) -> Dict[str, int]:
        try:
            return {camera_id: len(self._frame_dictionaries[camera_id]["frames_list"]) for camera_id in self._camera_ids}
        except KeyError:
            return {camera_id: 0 for camera_id in self._camera_ids}


    @property
    def recording_frames(self):
        return self._recording_frames

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        return self._latest_frames

    def check_if_camera_is_ready(self, cam_id: str) -> bool:
        for process in self._processes:
            if cam_id in process.camera_ids:
                return process.check_if_camera_is_ready(cam_id)


    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
            camera_config_dict: Dict[str, CameraConfig],
    ):

        for process in self._processes:
            process.start_capture(
                event_dictionary=event_dictionary, camera_config_dict=camera_config_dict
            )

    def _create_processes(
            self, camera_ids: List[str], cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ):
        if len(camera_ids) == 0:
            raise ValueError("No cameras were provided")
        camera_subarrays = array_split_by(camera_ids, cameras_per_process)
        processes = [
            CamGroupProcess(camera_ids=cam_id_subarray,
                            latest_frames=self._latest_frames,
                            frame_dictionaries=self._frame_dictionaries,
                            incoming_camera_configs=self._incoming_camera_configs,
                            recording_frames=self._recording_frames,
                            ) for cam_id_subarray in camera_subarrays
        ]
        cam_id_to_process = {}
        for process in processes:
            for cam_id in process.camera_ids:
                cam_id_to_process[cam_id] = process
        return processes, cam_id_to_process

    def update_camera_configs(self, camera_config_dictionary):
        logger.info(f"Updating camera configs: {camera_config_dictionary}")
        for process in self._processes:
            process.update_camera_configs(camera_config_dictionary)
