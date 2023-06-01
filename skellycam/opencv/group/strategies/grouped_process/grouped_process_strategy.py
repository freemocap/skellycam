import logging
import math
from time import perf_counter_ns
from typing import Dict, List

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.cam_group_process import (
    CamGroupProcess,
)
from skellycam.opencv.group.strategies.grouped_process.shared_camera_memory_manager import (
    SharedCameraMemoryManager,
)
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC
from skellycam.utilities.array_split_by import array_split_by
from skellycam.viewers.cv_cam_viewer import CvCamViewer

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

logger = logging.getLogger(__name__)


class GroupedProcessStrategy(StrategyABC):
    def __init__(self, camera_ids: List[str]):
        self._camera_ids = camera_ids
        self._shared_memory_manager = SharedCameraMemoryManager()

        self._create_shared_memory_objects()
        self._processes, self._cam_id_process_map = self._create_processes(
            camera_ids=self._camera_ids
        )

    def start_capture(self):
        """
        TODO: setup as coroutines or threadpool to parallelize the firing.
        """

        for process in self._processes:
            process.start_capture()

    def stop_capture(self):
        for process in self._processes:
            process.stop()

    def latest_frames_by_camera_id(self, camera_id: str):
        frames = self._frame_lists_by_camera[camera_id]
        return frames[-1]

    def is_camera_ready(self, cam_id: str) -> bool:
        for process in self._processes:
            if cam_id in process.camera_ids:
                return process.is_camera_ready(cam_id)

    @property
    def is_capturing(self):
        for process in self._processes:
            if not process.is_capturing:
                return False
        return True

    @property
    def known_frames_by_camera(self) -> Dict[str, List[FramePayload]]:
        return self._frame_lists_by_camera

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        return {
            camera_id: self.latest_frames_by_camera_id(camera_id)
            for camera_id in self._camera_ids
        }

    def _create_shared_memory_objects(self):
        self._frame_lists_by_camera = (
            self._shared_memory_manager.create_frame_lists_by_camera(
                keys=self._camera_ids
            )
        )
        self._should_record_controller = (
            self._shared_memory_manager.create_value(type="b", initial_value=False)
        )


    def _create_processes(
        self,
        camera_ids: List[str],
        cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS,
    ):
        if len(camera_ids) == 0:
            raise ValueError("No cameras were provided")
        camera_group_subarrays = array_split_by(camera_ids, cameras_per_process)


        processes = [
            CamGroupProcess(
                camera_ids=cam_id_subarray,
                frame_repository=self._frame_lists_by_camera,
                should_record_controller=self._should_record_controller,
            )
            for cam_id_subarray in camera_group_subarrays
        ]
        cam_id_to_process = {}
        for process in processes:
            for cam_id in process.camera_ids:
                cam_id_to_process[cam_id] = process
        return processes, cam_id_to_process


if __name__ == "__main__":
    p = GroupedProcessStrategy(camera_ids=["0"])
    p.start_capture()

    cv = CvCamViewer()
    cv.begin_viewer("0")
    while True:
        curr = perf_counter_ns() * 1e-6
        frame = p.latest_frames["0"]
        cv.recv_img(frame)
        if frame:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
