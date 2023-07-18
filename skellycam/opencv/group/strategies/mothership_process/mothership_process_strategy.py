import inspect
import logging
import multiprocessing
import threading
import time
from copy import deepcopy

from typing import List, Dict

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.shared_memory.shared_camera_memory_manager import \
    SharedCameraMemoryManager
from skellycam.opencv.group.strategies.mothership_process.mothership_process import MothershipProcess
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC

logger = logging.getLogger(__name__)


class MothershipProcessStrategy(StrategyABC):
    def __init__(self,
                 camera_ids: List[str], ):
        self._camera_ids = camera_ids
        self._shared_memory_manager = SharedCameraMemoryManager()
        self._received_frames_lists_by_camera = self._shared_memory_manager.create_frame_lists_by_camera(self._camera_ids)
        self._incoming_frames_queues_by_camera = {camera_id: multiprocessing.Queue() for camera_id in self._camera_ids}
        self._latest_frame_by_camera = self._shared_memory_manager.create_latest_frames_by_camera_dictionary(self._camera_ids)

        self._stop_event = multiprocessing.Event()

        self._mothership_process = MothershipProcess(
            name=f"Camera Mothership Process - Cameras {self._camera_ids}",
            camera_ids=self._camera_ids,
            incoming_frames_queues_by_camera=self._incoming_frames_queues_by_camera,
            latest_frame_by_camera=self._latest_frame_by_camera,
            stop_event=self._stop_event,
        )

    def start_capture(self):
        logger.info(f"Starting mothership process")
        self._mothership_process.start()

    def stop_capture(self):
        logger.info(f"Stopping mothership process")
        self._stop_event.set()


    @property
    def is_capturing(self):
        return self._mothership_process.is_capturing

    def is_recording(self):
            print(inspect.currentframe().f_code.co_name)

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        latest_frames = {}
        for camera_id in self._camera_ids:
            try:
                latest_frames[camera_id] = self._latest_frame_by_camera[camera_id]
            except Exception as e:
                latest_frames[camera_id] = None

        return latest_frames

    def latest_frames_by_camera_id(self, camera_id: str):
            print(inspect.currentframe().f_code.co_name)

    def start_recording(self, video_save_paths: dict):
            print(inspect.currentframe().f_code.co_name)

    def stop_recording(self):
            print(inspect.currentframe().f_code.co_name)
