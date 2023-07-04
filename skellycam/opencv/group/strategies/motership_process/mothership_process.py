import logging
import multiprocessing
import threading
import time
from multiprocessing import Process
from typing import List, Dict

from skellycam.opencv.group.strategies.grouped_process.cam_group_process.queue.grouped_process_queue_strategy import \
    GroupedProcessQueueStrategy
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.shared_memory.grouped_process_shared_memory_strategy import \
    GroupedProcessSharedMemoryStrategy
from skellycam.opencv.group.strategies.motership_process.multi_frame_payload_model import MultiFramePayload

logger = logging.getLogger(__name__)


def frame_puller(
        incoming_frames_queues_by_camera: Dict[str, multiprocessing.Queue],
        outgoing_frames_queues_by_camera: Dict[str, multiprocessing.Queue],
        stop_event: multiprocessing.Event,
):
    logger.info(f"Starting frame puller daemon")
    sleep_time = 1
    last_frame_tik = 0
    while not stop_event.is_set():
        time.sleep(sleep_time)

        qsizes = {camera_id: {"incoming": 0, "outgoing": 0} for camera_id in incoming_frames_queues_by_camera.keys()}
        for camera_id in incoming_frames_queues_by_camera.keys():
            qsizes[camera_id]["incoming"] = incoming_frames_queues_by_camera[camera_id].qsize()
            qsizes[camera_id]["outgoing"] = outgoing_frames_queues_by_camera[camera_id].qsize()

        print(
            f"Frame Puller Loop - Queue Sizes {qsizes} - Loop interval: {sleep_time} seconds")

        if any([queue.qsize() > 0 for queue in incoming_frames_queues_by_camera.values()]):
            for camera_id, incoming_queue in incoming_frames_queues_by_camera.items():
                if incoming_queue.qsize() > 0:
                    outgoing_frames_queues_by_camera[camera_id].put(incoming_queue.get())

            if sleep_time == 1:
                logger.info(
                    f"Frames available! Speeding up frame puller daemon, loop interval: {sleep_time} seconds")
                sleep_time = 0.001
            last_frame_tik = time.perf_counter()
        else:
            if time.perf_counter() - last_frame_tik > 1:
                sleep_time = 1
                logger.info(
                    f"No frames received in the last second. Slowing down frame puller daemon, loop interval: {sleep_time} seconds")
                last_frame_tik = 0

    while any([queue.qsize() > 0 for queue in incoming_frames_queues_by_camera.values()]):
        for camera_id, incoming_queue in incoming_frames_queues_by_camera.items():
            if incoming_queue.qsize() > 0:
                outgoing_frames_queues_by_camera[camera_id].put(incoming_queue.get())

class MothershipProcess(Process):
    def __init__(self,
                 name: str,
                 camera_ids: List[str],
                 incoming_frames_queues_by_camera: Dict[str, multiprocessing.Queue],
                 outgoing_frames_queues_by_camera: Dict[str, multiprocessing.Queue],
                 stop_event: multiprocessing.Event,
                 strategy: str = "queue",
                 ):
        super().__init__(name=name)
        self._camera_ids = camera_ids
        self._strategy = strategy
        self._incoming_frames_queues_by_camera = incoming_frames_queues_by_camera  # frames coming from the cameras
        self._outgoing_frames_queues_by_camera = outgoing_frames_queues_by_camera  # frames being sent up to mothership, who will route to GUI, save to disk, etc
        self._stop_event = stop_event
        self._grouped_process_strategy = None


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
                                                                         stop_event=self._stop_event)
        self._grouped_process_strategy.start_capture()

        self._frame_puller_thread = threading.Thread(target=frame_puller,
                                                     args=(self._incoming_frames_queues_by_camera,
                                                           self._outgoing_frames_queues_by_camera,
                                                           self._stop_event),
                                                     daemon=True,
                                                     name="Main Process - Frame Puller")
        self._frame_puller_thread.start()
        self._frame_puller_thread.join()
