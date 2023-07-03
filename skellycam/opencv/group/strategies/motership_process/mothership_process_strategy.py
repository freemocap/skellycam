import inspect
import logging
import multiprocessing
from typing import List, Dict

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.motership_process.mothership_process import MothershipProcess
from skellycam.opencv.group.strategies.motership_process.multi_frame_payload_model import MultiFramePayload
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC

logger = logging.getLogger(__name__)


class MothershipProcessStrategy(StrategyABC):
    def __init__(self,
                 camera_ids: List[str], ):
        self._camera_ids = camera_ids
        self._queue = multiprocessing.Queue()

        self._mothership_process = MothershipProcess(
            name=f"Camera Mothership Process - Cameras {self._camera_ids}",
            camera_ids=self._camera_ids,
            queue=self._queue,
        )

    def start_capture(self):
        print(f"Starting mothership process")
        self._mothership_process.start()

    def stop_capture(self):
        print(f"Stopping mothership process")
        self._mothership_process.terminate()

    def frame_databases_by_camera(self):
        pass

    @property
    def is_capturing(self):
        return self._mothership_process.is_capturing

    def is_recording(self):
            print(inspect.currentframe().f_code.co_name)

    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        print("Getting latest frames")
        if not self._queue.empty():
            multi_frame_payload = self._queue.get()
            assert isinstance(multi_frame_payload,
                              MultiFramePayload), f"Expected MultiFramePayload, got {type(multi_frame_payload)}"
            print(f"Multi frame payload {multi_frame_payload}")
            return multi_frame_payload.frames
        logger.debug(f"Latest frames not available")

    def latest_frames_by_camera_id(self, camera_id: str):
            print(inspect.currentframe().f_code.co_name)

    def start_recording(self, video_save_paths: dict):
            print(inspect.currentframe().f_code.co_name)

    def stop_recording(self):
            print(inspect.currentframe().f_code.co_name)
