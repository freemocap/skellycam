import logging
import multiprocessing
from multiprocessing import Process
from typing import List, Dict, Union

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.queue.grouped_process_queue_strategy import \
    GroupedProcessQueueStrategy
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.shared_memory.grouped_process_shared_memory_strategy import \
    GroupedProcessSharedMemoryStrategy
from skellycam.opencv.group.strategies.mothership_process.frame_puller_daemon import FramePullerDaemon

logger = logging.getLogger(__name__)


class MothershipProcess(Process):
    def __init__(self,
                 name: str,
                 camera_ids: List[str],
                 incoming_frames_queues_by_camera: Dict[str, multiprocessing.Queue],
                 latest_frame_by_camera: Dict[str, FramePayload],
                 stop_event: multiprocessing.Event,
                 strategy: str = "queue",
                 ):
        super().__init__(name=name)
        self._camera_ids = camera_ids
        self._strategy = strategy
        self._incoming_frames_queues_by_camera = incoming_frames_queues_by_camera  # frames coming from the cameras
        self._latest_frame_by_camera = latest_frame_by_camera  # latest frame received from each camera

        self._stop_event = stop_event
        self._grouped_process_strategy = None

        self._frame_puller_daemon = None

    def run(self):
        self._start_capture()

    @property
    def is_capturing(self):
        if self._grouped_process_strategy is None:
            return False
        return self._grouped_process_strategy.is_capturing

    def _start_capture(self):
        if self._strategy == "shared_memory":
            self._grouped_process_strategy = GroupedProcessSharedMemoryStrategy(camera_ids=self._camera_ids)
        else:
            self._grouped_process_strategy = GroupedProcessQueueStrategy(camera_ids=self._camera_ids,
                                                                         frame_queues_by_camera=self._incoming_frames_queues_by_camera,
                                                                         latest_frame_by_camera=self._latest_frame_by_camera,
                                                                         stop_event=self._stop_event)
        self._grouped_process_strategy.start_capture()

        # self._frame_puller_daemon = FramePullerDaemon(
        #     incoming_frames_queues_by_camera=self._incoming_frames_queues_by_camera,
        #     received_frames_lists_by_camera=self._received_frames_lists_by_camera,
        #     stop_event=self._stop_event)
        #
        # self._frame_puller_daemon.start()

    def latest_frames(self) -> Union[None, Dict[str, FramePayload]]:

        latest_frames = {}
        for camera_id, frame_list in self._received_frames_lists_by_camera.items():
            latest_frames[camera_id] = None

            if len(frame_list):
                continue

            latest_frames[camera_id] = frame_list[-1]

        return latest_frames
