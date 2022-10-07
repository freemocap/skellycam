from typing import List

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.opencv.group.strategies.grouped_process_strategy import \
    GroupedProcessStrategy
from fast_camera_capture.opencv.group.strategies.strategies import Strategy


class CameraGroup:
    def __init__(self, strategy: Strategy):
        self._strategy_enum = strategy
        # Make optional, if a list of cams is sent then just use that
        cams = detect_cameras()
        self._strategy_class = self._resolve_strategy(cams.cameras_found_list)

    def start(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        self._strategy_class.start_capture()

    def get_by_cam_id(self, cam_id: str):
        return self._strategy_class.get_by_cam_id(cam_id)

    def _resolve_strategy(self, cams: List[str]):
        if self._strategy_enum == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(cams)
