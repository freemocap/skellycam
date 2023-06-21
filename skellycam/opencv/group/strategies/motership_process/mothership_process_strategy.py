import logging
import time
from multiprocessing import Process
from typing import List, Tuple

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.grouped_process_strategy import GroupedProcessStrategy
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC

logger = logging.getLogger(__name__)
class MothershipProcess(Process):
    def run(self):
        self._start_capture(self._args)

    def _start_capture(self,
                       camera_ids: Tuple[str],
                       ):
        camera_ids = list(camera_ids)
        grouped_process_strategy = GroupedProcessStrategy(camera_ids=camera_ids)
        grouped_process_strategy.start_capture()

        while grouped_process_strategy.is_capturing:
            time.sleep(1)
            print(f"Mothership process is alive. {grouped_process_strategy.is_capturing}")



class MothershipProcessStrategy(StrategyABC):
    def __init__(self,
                 camera_ids: Tuple[str], ):
        self._camera_ids = camera_ids
        self._mothership_process = MothershipProcess(
            name = f"Camera Mothership Process - Cameras {self._camera_ids}",
            args = self._camera_ids
        )

    def start_capture(self):
        print(f"Starting mothership process")
        self._mothership_process.start()

    def stop_capture(self):
        print(f"Stopping mothership process")
        self._mothership_process.terminate()

    def frame_databases_by_camera(self):
        pass

    def is_capturing(self):
        return self._mothership_process.is_alive()

    def is_recording(self):
        pass

    @property
    def latest_frames(self):
        dummy_frames  = {}
        for camera_id in self._camera_ids:
            dummy_frames[camera_id] = FramePayload(
                image = np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8),
            )
        return dummy_frames

    def latest_frames_by_camera_id(self, camera_id: str):
        pass

    def start_recording(self, video_save_paths: dict):
        pass

    def stop_recording(self):
        pass

