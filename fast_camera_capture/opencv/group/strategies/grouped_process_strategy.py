import multiprocessing
from typing import Dict, List

from fast_camera_capture.detection.models.frame_payload import FramePayload
from fast_camera_capture.opencv.camera.types.camera_id import CameraId
from fast_camera_capture.opencv.group.strategies.cam_group_queue_process import (
    CamGroupProcess,
)
from fast_camera_capture.utils.array_split_by import array_split_by

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2


# https://refactoring.guru/design-patterns/strategy


class GroupedProcessStrategy:
    def __init__(self, cam_ids: List[str]):
        self._processes, self._cam_id_process_map = self._create_processes(cam_ids)

    @property
    def processes(self):
        return self._processes

    @property
    def is_capturing(self):
        for process in self._processes:
            if not process.is_capturing:
                return False
        return True

    def start_capture(self, event_dictionary: Dict[str, multiprocessing.Event]):

        for process in self._processes:
            process.start_capture(event_dictionary=event_dictionary)


    def check_if_camera_is_ready(self, cam_id: str) -> bool:
        for process in self._processes:
                if cam_id in process.camera_ids:
                    return process.check_if_camera_is_ready(cam_id)

    def get_by_cam_id(self, cam_id: str):
        for process in self._processes:
            curr = process.get_by_cam_id(cam_id)
            if curr:
                return curr


    def get_latest_frames(self) -> Dict[CameraId, FramePayload]:
        return {
            cam_id: process.get_by_cam_id(cam_id)
            for cam_id, process in self._cam_id_process_map.items()
        }

    def _create_processes(
        self, cam_ids: List[str], cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS
    ):
        camera_subarrays = array_split_by(cam_ids, cameras_per_process)
        processes = [
            CamGroupProcess(cam_id_subarray) for cam_id_subarray in camera_subarrays
        ]
        cam_id_to_process = {}
        for process in processes:
            for cam_id in process.camera_ids:
                cam_id_to_process[cam_id] = process
        return processes, cam_id_to_process
