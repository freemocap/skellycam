import logging
import multiprocessing
import time
from typing import List, Union

from skellycam.backend.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


class BackendController:
    def __init__(self,
                 camera_ids: List[str],
                 queue: multiprocessing.Queue,
                 exit_event: multiprocessing.Event):
        self._queue = queue
        self._exit_event = exit_event

        self._process = multiprocessing.Process(target=self._run_camera_group_process,
                                          args=(camera_ids,
                                                self._queue,
                                                self._exit_event))


    def start_camera_group_process(self):
        self._process.start()
        logger.info(f"Started camera group process")

    @staticmethod
    def _run_camera_group_process(camera_ids: List[int],
                                  queue: multiprocessing.Queue,
                                  exit_event: multiprocessing.Event):
        logger.info(f"Starting camera group process for camera_ids: {camera_ids}")
        camera_group = create_camera_group(camera_ids)
        queue.put({"type": "camera_group_created",
                   "camera_config_dictionary": camera_group.camera_config_dictionary})
        camera_group.start()
        should_continue = True
        logger.info("Emitting `cameras_connected_signal`")
        queue.put({"type": "cameras_connected"})

        while camera_group.is_capturing and should_continue and not exit_event.is_set():

            new_frames = camera_group.new_frames()
            if len(new_frames) > 0:
                logger.trace(f"Stuffing latest frames into pipe: {list(new_frames.keys())} - queue size: {queue.qsize()}")
                for camera_id, frame_payload in new_frames.items():
                    if not camera_id == frame_payload.camera_id:
                        raise ValueError(f"camera_id: {camera_id} != frame_payload.camera_id: {frame_payload.camera_id}")
                    queue.put({"type": "new_frame",
                               "frame": frame_payload})


def create_camera_group(camera_ids: List[Union[str, int]], camera_config_dictionary: dict = None
                        ):
    logger.info(
        f"Creating `camera_group` for camera_ids: {camera_ids}, camera_config_dictionary: {camera_config_dictionary}"
    )

    camera_group = CameraGroup(
        camera_ids_list=camera_ids,
        camera_config_dictionary=camera_config_dictionary,
    )
    return camera_group
