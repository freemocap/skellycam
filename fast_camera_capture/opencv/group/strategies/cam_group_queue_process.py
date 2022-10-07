import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns
from typing import Dict, List

from fast_camera_capture import CamArgs, Camera
from fast_camera_capture.detection.models.frame_payload import FramePayload
from fast_camera_capture.opencv.group.strategies.queue_communicator import QueueCommunicator


class CamGroupProcess:
    def __init__(self, cam_ids: List[str]):
        self._cam_ids = cam_ids
        self._process: Process = None
        self._payload = None
        communicator = QueueCommunicator(cam_ids)
        self._queues = communicator.queues

    def start_capture(self):
        self._process = Process(target=CamGroupProcess._begin, args=(self._cam_ids, self._queues))
        self._process.start()

    @staticmethod
    def _create_cams(cam_ids: List[str]):
        return [Camera(CamArgs(cam_id=cam)) for cam in cam_ids]

    @staticmethod
    def _begin(cam_ids: List[str], queues: Dict[str, multiprocessing.Queue]):
        cameras = CamGroupProcess._create_cams(cam_ids)
        for cam in cameras:
            cam.connect()
        while True:
            for cam in cameras:
                if cam.new_frame_ready:
                    queue = queues[cam.cam_id]
                    queue.put_nowait(cam.latest_frame)

    def get_by_cam_id(self, cam_id) -> FramePayload | None:
        if cam_id not in self._queues:
            return

        queue = self._queues[cam_id]
        if not queue.empty():
            return queue.get()


if __name__ == "__main__":
    p = CamGroupProcess(["0"])
    p.start_capture()
    while True:
        curr = perf_counter_ns() * 1e-6
        frames = p.get_by_cam_id()
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
