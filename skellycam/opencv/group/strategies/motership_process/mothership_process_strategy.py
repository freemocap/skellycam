import inspect
import logging
import multiprocessing
import time
from multiprocessing import Process
from typing import List, Tuple, Dict

from pydantic import BaseModel

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.grouped_process_strategy import GroupedProcessStrategy
from skellycam.opencv.group.strategies.strategy_abc import StrategyABC

logger = logging.getLogger(__name__)


class MultiFramePayload(BaseModel):
    frames: Dict[str, FramePayload]
    statistics: Dict[str, Dict[str, float] ]=None
    synchronized: bool = False

    class Config:
        arbitrary_types_allowed = True


class MothershipProcess(Process):
    def __init__(self,
                 name: str,
                 camera_ids: List[str],
                 pipe_connection_child: multiprocessing.connection.Connection,
                 ):
        super().__init__(name=name)
        self._camera_ids = camera_ids
        self._pipe_connection_child = pipe_connection_child
        self._grouped_process_strategy = None

    def run(self):
        self._start_capture()

    @property
    def is_capturing(self):
        if self._grouped_process_strategy is None:
            return False
        return self._grouped_process_strategy.is_capturing

    def _start_capture(self):

        self._grouped_process_strategy = GroupedProcessStrategy(camera_ids=self._camera_ids)
        self._grouped_process_strategy.start_capture()

        multi_frame_count = 0
        while self._grouped_process_strategy.is_capturing:
            tic = time.perf_counter()
            latest_frames = self._grouped_process_strategy.latest_frames

            mutli_frame_payload = MultiFramePayload(
                frames=latest_frames,
            )
            self._pipe_connection_child.send(mutli_frame_payload)

            multi_frame_count += 1
            logger.info(
                f"Sending multi frame payload  # {multi_frame_count} - seconds per loop {time.perf_counter() - tic}")


class MothershipProcessStrategy(StrategyABC):
    def __init__(self,
                 camera_ids: List[str], ):
        self._camera_ids = camera_ids
        self._pipe_connection_parent, self._pipe_connection_child = multiprocessing.Pipe(duplex=True)

        self._mothership_process = MothershipProcess(
            name=f"Camera Mothership Process - Cameras {self._camera_ids}",
            camera_ids=self._camera_ids,
            pipe_connection_child=self._pipe_connection_child,

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
        if self._pipe_connection_parent.poll():
            multi_frame_payload = self._pipe_connection_parent.recv()
            assert isinstance(multi_frame_payload,
                              MultiFramePayload), f"Expected MultiFramePayload, got {type(multi_frame_payload)}"
            return multi_frame_payload.frames
        logger.debug(f"Latest frames not available")

    def latest_frames_by_camera_id(self, camera_id: str):
            print(inspect.currentframe().f_code.co_name)

    def start_recording(self, video_save_paths: dict):
            print(inspect.currentframe().f_code.co_name)

    def stop_recording(self):
            print(inspect.currentframe().f_code.co_name)
