import logging
import multiprocessing
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from PyQt6.QtCore import pyqtSignal

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.grouped_process_strategy import (
    GroupedProcessStrategy,
)
from skellycam.opencv.group.strategies.strategies import Strategy
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC
from skellycam.opencv.group.wait_for_all_cameras import StartSynchronizer, WaitArgs
from skellycam.opencv.video_recorder.video_save_background_process.video_save_background_process import (
    VideoSaveBackgroundProcess,
)
from skellycam.viewers.cv_cam_viewer import CvCamViewer

logger = logging.getLogger(__name__)


class CameraGroup:
    def __init__(
        self,
        camera_ids_list: List[str],
        strategy: Strategy = Strategy.X_CAM_PER_PROCESS,
    ):
        self._selected_strategy = strategy
        self._camera_ids = camera_ids_list

        self._strategy_class = self._resolve_strategy(camera_ids=self._camera_ids)

    def start_capture(self):
        """
        Creates new processes to manage cameras. Use the `get` API to grab camera frames
        :return:
        """
        logger.info(f"Starting camera group with strategy {self._selected_strategy}")
        self._strategy_class.start_capture()
        # self._start_video_save_background_process()
        logger.info(f"All cameras {self._camera_ids} started!")

    def get_latest_frame_by_camera_id(self, camera_id: str):
        return self._strategy_class.latest_frames_by_camera_id(camera_id)

    def stop(self):
        self._strategy_class.stop_capture()
        # self._video_save_background_process.terminate()

    @property
    def is_capturing(self):
        return self._strategy_class.is_capturing

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        return self._strategy_class.latest_frames

    def _start_video_save_background_process(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._video_save_background_process = VideoSaveBackgroundProcess(
            frame_lists_by_camera=self._strategy_class.known_frames_by_camera,
        )
        self._video_save_background_process.start()

    def _resolve_strategy(self, camera_ids: List[str]) -> StrategyABC:
        if self._selected_strategy == Strategy.X_CAM_PER_PROCESS:
            return GroupedProcessStrategy(
                camera_ids=camera_ids,
            )

        raise Exception("No strategy found")


if __name__ == "__main__":
    cams = ["0"]
    g = CameraGroup(cams)
    g.start_capture()
    viewer = CvCamViewer()
    viewer.begin_viewer("0")

    while True:
        time.sleep(0.001)
        frame = g.get_latest_frame_by_camera_id("0")
        viewer.recv_img(frame)
