import math
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import List

import cv2
import zmq

from skellycam import Camera, CameraConfig


class CamGroupZeromqProcess:
    def __init__(self, cam_ids: List[str]):
        self._cam_ids = cam_ids
        self._process: Process = None
        self._payload = None
        parent_zmq = zmq.Context()
        self._parent_recv = parent_zmq.socket(zmq.PULL)
        self._parent_recv.connect("tcp://127.0.0.1:5556")

    def start_capture(self):
        self._process = Process(
            target=CamGroupZeromqProcess._begin, args=(self._cam_ids,)
        )
        self._process.start()
        while not self._process.is_alive():
            sleep(0.01)

    @staticmethod
    def _create_cams(cam_ids: List[str]):
        return [Camera(CameraConfig(cam_id=cam)) for cam in cam_ids]

    @staticmethod
    def _begin(cam_ids: List[str]):
        cameras = CamGroupZeromqProcess._create_cams(cam_ids)
        child_zmq = zmq.Context()
        send = child_zmq.socket(zmq.PUSH)
        send.bind("tcp://127.0.0.1:5556")
        for cam in cameras:
            cam.connect()
        while True:
            for cam in cameras:
                if cam.new_frame_ready:
                    send.send_pyobj(cam.latest_frame)

    def get(self, cam_id: str = ""):
        return self._parent_recv.recv_pyobj()


if __name__ == "__main__":
    p = CamGroupZeromqProcess(["0"])
    p.start_capture()
    while True:
        curr = perf_counter_ns() * 1e-6
        frames = p.get()
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
