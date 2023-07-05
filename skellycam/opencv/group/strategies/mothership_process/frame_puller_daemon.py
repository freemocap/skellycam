import logging
import multiprocessing
import threading
import time
from copy import deepcopy
from typing import Dict, Any

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.cam_group_process.shared_memory.shared_camera_memory_manager import \
    SharedCameraMemoryManager

logger = logging.getLogger(__name__)
class FramePullerDaemon(threading.Thread):
    def __init__(
            self,
            incoming_frames_queues_by_camera: Dict[str, multiprocessing.Queue],
            received_frames_lists_by_camera: Dict[str, Any],
            stop_event: multiprocessing.Event,
        ):
        super().__init__(daemon=True,
                         name="FramePullerDaemon")
        self._incoming_frames_queues_by_camera = incoming_frames_queues_by_camera
        self._received_frames_lists_by_camera = received_frames_lists_by_camera
        self._stop_event = stop_event


    @property
    def latest_frames(self) -> Dict[str, FramePayload]:
        latest_frames = {}
        for camera_id, received_frames_list in self._received_frames_lists_by_camera.items():
            if len(received_frames_list) > 0:
                latest_frames[camera_id] = deepcopy(received_frames_list[-1])
            else:
                latest_frames[camera_id] = None

        return latest_frames

    def run(self):
        logger.info(f"Starting frame puller daemon")
        sleep_time = 1
        last_frame_tik = 0
        cameras_ready = {camera_id: False for camera_id in self._incoming_frames_queues_by_camera.keys()}
        while not self._stop_event.is_set():
            time.sleep(sleep_time)

            qsizes = {camera_id: {"incoming": 0, "outgoing": 0} for camera_id in self._incoming_frames_queues_by_camera.keys()}
            for camera_id in self._incoming_frames_queues_by_camera.keys():
                qsizes[camera_id]["incoming"] = self._incoming_frames_queues_by_camera[camera_id].qsize()
                qsizes[camera_id]["outgoing"] = len(self._received_frames_lists_by_camera[camera_id])

            print(
                f"Frame Puller Loop - Queue Sizes {qsizes} - Loop interval: {sleep_time} seconds")

            if any([queue.qsize() > 0 for queue in self._incoming_frames_queues_by_camera.values()]):
                for camera_id, incoming_queue in self._incoming_frames_queues_by_camera.items():
                    if incoming_queue.qsize() > 0:
                        frame = incoming_queue.get()
                        cameras_ready[camera_id] = True

                        if all(list(cameras_ready.values())):
                            self._received_frames_lists_by_camera[camera_id].append(frame)

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

        while any([queue.qsize() > 0 for queue in self._incoming_frames_queues_by_camera.values()]):
            for camera_id, incoming_queue in self._incoming_frames_queues_by_camera.items():
                if incoming_queue.qsize() > 0:
                    self._received_frames_lists_by_camera[camera_id].append(incoming_queue.get())
