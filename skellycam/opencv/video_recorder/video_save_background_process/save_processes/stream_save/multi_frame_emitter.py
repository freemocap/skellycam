import concurrent
import logging
import multiprocessing
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from multiprocessing import Queue
from typing import Any, Dict, Callable

logger = logging.getLogger(__name__)


class MultiFrameEmitter(threading.Thread):
    def __init__(self, frame_databases_by_camera):
        super().__init__()

        self._camera_ids = list(frame_databases_by_camera.keys())
        self._frame_databases_by_camera_id = frame_databases_by_camera

        self._frame_queues = {camera_id: Queue() for camera_id in self._camera_ids}  # Queue to receive frames

        self._multi_frame_creator_thread = threading.Thread(target=self._create_multi_frames)
        self._multi_frame_pipe_parent, self._multi_frame_pipe_child = multiprocessing.Pipe()
        self._latest_multi_frame_lock = threading.Lock()
        self._stop = threading.Event()

        self._multi_frame_ready = False
        self._latest_multi_frame = None

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def multi_frame_pipe_child(self):
        return self._multi_frame_pipe_child

    @property
    def multi_frame_ready(self):
        return self._multi_frame_ready

    def run(self):
        with ThreadPoolExecutor(max_workers=len(self._camera_ids) + 1) as executor:
            futures = {executor.submit(self._receive_frames,
                                       camera_id=camera_id,
                                       frame_database=frame_database,
                                       stop=self._stop,
                                       frame_queue=self._frame_queues[camera_id],
                                       get_latest_frame=self._get_latest_frame) for camera_id, frame_database in
                       self._frame_databases_by_camera_id.items()}
            futures.add(executor.submit(self._create_multi_frames))

            while not self._stop.is_set():
                time.sleep(0.001)
                done, not_done = concurrent.futures.wait(futures, timeout=0)
                for future in done:
                    logger.info(f"concurrent.future thread:  {future}  - completed")
                    pass
                futures = not_done

    @staticmethod
    def _receive_frames(camera_id: str,
                        frame_database: Dict[str, Any],
                        stop: threading.Event,
                        frame_queue: Queue,
                        get_latest_frame: Callable, ):

        logger.info(f"Starting frame receiver thread for Camera: {camera_id}")
        while not stop.is_set():
            time.sleep(0.001)

            if frame_database["latest_frame_index"].value <= frame_database["read_frame_index"].value:
                # No new frames
                continue

            frame = get_latest_frame(frame_database)
            if frame:
                pass
                # frame_queue.put(frame)

    @staticmethod
    def _get_latest_frame(frame_database):
        try:
            if frame_database["total_frame_write_count"].value < frame_database["total_frame_read_count"].value:
                raise ValueError("Frame reader got ahead of frame writer!")
        except ValueError as e:
            logger.error(f"Error: {e}")

        frame_database["read_frame_index"].value += 1
        frame_list = frame_database["frames"]
        read_frame_index = (frame_database["read_frame_index"].value) % len(frame_list)
        # copy the frame data, which should be a 'read' operation that won't block the IPC process writing new frames?
        frame = deepcopy(frame_list[read_frame_index])
        if frame:
            frame_database["total_frame_read_count"].value += 1
        return frame

    def stop(self):
        self._stop.set()

    def _create_multi_frames(self):
        count = 0
        while not self._stop.is_set():
            time.sleep(0.001)
            frame_queues_ready = not all([self._frame_queues[camera_id].empty() for camera_id in self._camera_ids])
            if frame_queues_ready:
                multi_frame = {camera_id: self._frame_queues[camera_id].get() for camera_id in self._camera_ids}

                self._multi_frame_pipe_parent.send(multi_frame)
                count += 1
                print(f"Multi-frame# {count} created")
