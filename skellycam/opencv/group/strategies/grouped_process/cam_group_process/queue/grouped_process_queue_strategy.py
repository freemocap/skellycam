import logging
import math
import multiprocessing
from time import perf_counter_ns
from typing import Dict, List, Union

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.queue.cam_group_queue_process import \
    CamGroupQueueProcess
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC
from skellycam.utilities.array_split_by import array_split_by
from skellycam.viewers.cv_cam_viewer import CvCamViewer

### Don't change this? Users should submit the actual value they want
### this is our library default.
### This should only change based off of real world experimenting with CPUs
_DEFAULT_CAM_PER_PROCESS = 2

# https://refactoring.guru/design-patterns/strategy

logger = logging.getLogger(__name__)


class GroupedProcessQueueStrategy(StrategyABC):
    def __init__(self,
                 camera_ids: List[str],
                 frame_queues_by_camera: Dict[str, multiprocessing.Queue],
                 stop_event: multiprocessing.Event, ):
        self._camera_ids = camera_ids
        self._stop_event = stop_event

        self._frame_queues_by_camera = frame_queues_by_camera

        self._processes, self._cam_id_process_map = self._create_processes(
            camera_ids=self._camera_ids
        )

    def start_capture(self):
        """
        Connect to cameras and start reading frames.
        TODO: setup as coroutines or threadpool to parallelize the firing.
        """

        for process in self._processes:
            process.start_capture()
        # self._multi_frame_emitter.start()
        # self._video_save_process.start()

    def stop_capture(self):
        """Shut down camera processes (and disconnect from cameras)"""
        logger.info("Stopping capture by setting stop event")
        self._stop_event.set()



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


    def _create_processes(
            self,
            camera_ids: List[str],
            cameras_per_process: int = _DEFAULT_CAM_PER_PROCESS,
    ):
        if len(camera_ids) == 0:
            raise ValueError("No cameras were provided")

        camera_group_subarrays = array_split_by(camera_ids, cameras_per_process)

        processes = [
            CamGroupQueueProcess(
                camera_ids=cam_id_subarray,
                frame_queues_by_camera=self._frame_queues_by_camera,
                stop_event=self._stop_event,
            )
            for subarray_number, cam_id_subarray in enumerate(camera_group_subarrays)
        ]
        cam_id_to_process = {}
        for process in processes:
            for cam_id in process.camera_ids:
                cam_id_to_process[cam_id] = process
        return processes, cam_id_to_process


if __name__ == "__main__":
    p = GroupedProcessQueueStrategy(camera_ids=["0"])
    p.start_capture()

    cv = CvCamViewer()
    cv.begin_viewer("0")
    while True:
        curr = perf_counter_ns() * 1e-6
        frame_ = p.latest_frames["0"]
        cv.recv_img(frame_)
        if frame_:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
