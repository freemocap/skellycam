import logging
import multiprocessing
from typing import List, Union

import cv2
import numpy as np

from skellycam.backend.charuco.charuco_detection import draw_charuco_on_image
from skellycam.backend.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


class BackendProcessController:
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
                                  exit_event: multiprocessing.Event,
                                  annotate_images: bool = False):
        logger.info(f"Starting camera group process for camera_ids: {camera_ids}")
        camera_group = create_camera_group(camera_ids)
        queue.put({"type": "camera_group_created",
                   "camera_config_dictionary": camera_group.camera_config_dictionary})
        camera_group.start()

        logger.info("Emitting `cameras_connected_signal`")
        queue.put({"type": "cameras_connected"})

        while camera_group.is_capturing and not exit_event.is_set():

            new_frames = camera_group.new_frames()
            if len(new_frames) > 0:
                logger.trace(
                    f"Stuffing latest frames into pipe: {list(new_frames.keys())} - queue size: {queue.qsize()}")

                for camera_id, frame_payload in new_frames.items():
                    if not camera_id == frame_payload.camera_id:
                        raise ValueError(
                            f"camera_id: {camera_id} != frame_payload.camera_id: {frame_payload.camera_id}")

                    image_for_frontend = prepare_image_for_frontend(image=frame_payload.image,
                                                                    annotate_image=annotate_images)

                    frame_info = BackendProcessController._extract_frame_stats(camera_id, frame_payload, queue)
                    queue.put({"type": "new_image",
                               "image": image_for_frontend,
                               "frame_info": frame_info})

    @staticmethod
    def _extract_frame_stats(camera_id, frame_payload, queue):
        frame_info = {"camera_id": camera_id,
                      "timestamp_ns": frame_payload.timestamp_ns,
                      "number_of_frames_received": frame_payload.number_of_frames_received,
                      "number_of_frames_recorded": frame_payload.number_of_frames_recorded,
                      "queue_size": queue.qsize()}
        return frame_info


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


def prepare_image_for_frontend(image: np.ndarray,
                               annotate_image: bool) -> np.ndarray:
    if annotate_image:
        image = draw_charuco_on_image(image)

    # image = cv2.flip(image, 1)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image_scaled = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)
    return image_scaled
