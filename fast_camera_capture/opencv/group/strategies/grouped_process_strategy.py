from typing import List

import numpy as np

from fast_camera_capture.opencv.group.strategies.cam_group_queue_process import CamGroupProcess

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2


class GroupedProcessStrategy:
    def __init__(self, cam_ids: List[str]):
        self._processes = self._create_processes(cam_ids)

    def start_capture(self):
        for process in self._processes:
            process.start_capture()

    def get_by_cam_id(self, cam_id: str):
        for process in self._processes:
            return process.get_by_cam_id(cam_id)

    def _create_processes(self, cam_ids: List[str],
        cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS):
        ## Split code
        cam_ids_as_nparray = np.array(cam_ids)
        cam_ids_split_nparray = np.array_split(cam_ids_as_nparray, cameras_per_process)
        camera_subarrays = [subarray.tolist() for subarray in cam_ids_split_nparray]

        return [CamGroupProcess(cam_id_subarray) for cam_id_subarray in camera_subarrays]
