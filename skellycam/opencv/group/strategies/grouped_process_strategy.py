import logging
import multiprocessing
from typing import Dict, List

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.cam_group_queue_process import CamGroupQueueProcess
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
    def queue_size(self) -> Dict[str, int]:
        return {camera_id: self._get_queue_size_by_camera_id(camera_id) for camera_id in self._camera_ids}

    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
            camera_config_dict: Dict[str, CameraConfig],
    ):

        for process in self._processes:
            process.start_capture(
                event_dictionary=event_dictionary, camera_config_dict=camera_config_dict
            )

    def check_if_camera_is_ready(self, cam_id: str) -> bool:
        for process in self._processes:
            if cam_id in process.camera_ids:
                return process.check_if_camera_is_ready(cam_id)

    def get_current_frame_by_cam_id(self, camera_id: str):
        for process in self._processes:
            current_frame = process.get_current_frame_by_camera_id(camera_id)
            if current_frame:
                return current_frame

    def _get_queue_size_by_camera_id(self, camera_ids: str) -> int:
        for process in self._processes:
            if camera_ids in process.camera_ids:
                return process.get_queue_size_by_camera_id(camera_ids)

    def get_latest_frames(self) -> Dict[str, FramePayload]:
        return {
            cam_id: process.get_current_frame_by_camera_id(cam_id)
            for cam_id, process in self._cam_id_process_map.items()
        }

    def _create_processes(
            self, cam_ids: List[str], cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ):
        if len(cam_ids) == 0:
            raise ValueError("No cameras were provided")
        camera_subarrays = array_split_by(cam_ids, cameras_per_process)
        processes = [
            CamGroupQueueProcess(cam_id_subarray) for cam_id_subarray in camera_subarrays
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
