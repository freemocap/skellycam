import multiprocessing
import time
from multiprocessing import Process
from typing import List

from skellycam.opencv.group.strategies.grouped_process.grouped_process_strategy import GroupedProcessStrategy
from skellycam.opencv.group.strategies.motership_process.multi_frame_payload_model import MultiFramePayload


class MothershipProcess(Process):
    def __init__(self,
                 name: str,
                 camera_ids: List[str],
                 queue: multiprocessing.Queue,
                 ):
        super().__init__(name=name)
        self._camera_ids = camera_ids
        self._queue = queue
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

            multi_frame_payload = MultiFramePayload(
                frames=latest_frames,
                multi_frame_number=multi_frame_count,
            )
            self._queue.put(multi_frame_payload)

            multi_frame_count += 1
            print(
                f"Sending multi frame payload  # {multi_frame_payload.multi_frame_number} - seconds per loop {time.perf_counter() - tic:.4f} - Queue size {self._queue.qsize()}")
