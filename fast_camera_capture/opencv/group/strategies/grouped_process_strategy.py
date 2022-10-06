from multiprocessing import Process
from typing import List

import numpy as np

DEFAULT_CAM_PER_PROCESS = 2


class GroupedProcessStrategy:
    def __init__(self):
        pass

    def tryit(self, cam_ids: List[str], cameras_per_process: int = DEFAULT_CAM_PER_PROCESS):
        ## Split code
        cam_ids_as_nparray = np.array(cam_ids)
        cam_ids_split_nparray = np.array_split(cam_ids_as_nparray, cameras_per_process)
        camera_subarrays = [subarray.tolist() for subarray in cam_ids_split_nparray]

        process_count = len(camera_subarrays)

        for curr in process_count:
            process = Process()
        return camera_subarrays


if __name__ == "__main__":
    s = GroupedProcessStrategy()
    arr = s.tryit(["1", "2", "3", "4", "5"], 2)
    print(arr)
