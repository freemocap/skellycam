from typing import List

from fast_camera_capture.opencv.group.strategies.strategies import Strategy


class CameraGroup:
    def __init__(self, strategy: Strategy):
        self._strategy = strategy

    def start(self, cam_ids: List[str]):
        pass