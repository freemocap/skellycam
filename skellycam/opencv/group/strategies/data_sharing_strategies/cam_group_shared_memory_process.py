import logging
import math
import multiprocessing
from multiprocessing import Process

from time import perf_counter_ns, sleep
from typing import Dict, List, Union

import numpy as np
from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.data_sharing_strategies.utilities.queue_communicator import QueueCommunicator

logger = logging.getLogger(__name__)

CAMERA_CONFIG_DICT_QUEUE_NAME = "camera_config_dict_queue"


class CamGroupSharedMemoryProcess:
    """
    Keeps a shared memory array for each camera to share the latest image with the main process.
    Frame timestamps and whatnot are shared through the same QueueCommunicator as the the original `CameraGroupQueueProcess`
    https://medium.com/analytics-vidhya/using-numpy-efficiently-between-processes-1bee17dcb01
    https://superfastpython.com/multiprocessing-shared-ctypes-in-python/
    """

    def __init__(self, camera_ids: List[str]):
        super().__init__()
        self._shared_memory_image_dictionary = None
        if len(camera_ids) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._cameras_ready_event_dictionary = None
        self._camera_ids = camera_ids
        self._process: Process = None
        self._payload = None
        queue_name_list = self._camera_ids.copy()
        queue_name_list.append(CAMERA_CONFIG_DICT_QUEUE_NAME)
        communicator = QueueCommunicator(queue_name_list)
        self._queues = communicator.queues

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def name(self):
        return self._process.name

    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
            camera_config_dict: Dict[str, CameraConfig],
    ):
        """
        Start capturing frames. Only return if the underlying process is fully running.
        :return:
        """

        logger.info(f"Starting capture `Process` for {self._camera_ids}")

        self._cameras_ready_event_dictionary = {
            camera_id: multiprocessing.Event() for camera_id in self._camera_ids
        }
        event_dictionary["ready"] = self._cameras_ready_event_dictionary

        self._shared_memory_image_dictionary = self._create_shared_memory_image_dictionary(
            camera_config_dict=camera_config_dict, )

        self._process = Process(
            name=f"Cameras {self._camera_ids}",
            target=CamGroupSharedMemoryProcess._begin,
            args=(
                self._camera_ids,
                self._shared_memory_image_dictionary,
                self._queues,
                event_dictionary, camera_config_dict),
        )
        self._process.start()
        while not self._process.is_alive():
            logger.debug(f"Waiting for Process {self._process.name} to start")
            sleep(0.25)

    @property
    def is_capturing(self):
        if self._process:
            return self._process.is_alive()
        return False

    def terminate(self):
        if self._process:
            self._process.terminate()
            logger.info(f"CamGroupProcess {self.name} terminate command executed")

    @staticmethod
    def _create_cams(camera_config_dict: Dict[str, CameraConfig]) -> Dict[str, Camera]:
        cam_dict = {
            camera_config.camera_id: Camera(camera_config)
            for camera_config in camera_config_dict.values()
        }
        return cam_dict

    @staticmethod
    def _begin(
            cam_ids: List[str],
            shared_memory_image_dictionary: Dict[str, multiprocessing.Array],
            queues: Dict[str, multiprocessing.Queue],
            event_dictionary: Dict[str, multiprocessing.Event],
            camera_config_dict: Dict[str, CameraConfig],
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {cam_ids}"
        )
        ready_event_dictionary = event_dictionary["ready"]
        start_event = event_dictionary["start"]
        exit_event = event_dictionary["exit"]

        setproctitle(f"Cameras {cam_ids}")

        process_camera_config_dict = {
            camera_id: camera_config_dict[camera_id] for camera_id in cam_ids
        }
        cameras_dictionary = CamGroupSharedMemoryProcess._create_cams(
            camera_config_dict=process_camera_config_dict
        )

        for camera in cameras_dictionary.values():
            camera.connect(ready_event_dictionary[camera.camera_id])

        while not exit_event.is_set():
            if not multiprocessing.parent_process().is_alive():
                logger.info(
                    f"Parent process is no longer alive. Exiting {cam_ids} process"
                )
                break

            if queues[CAMERA_CONFIG_DICT_QUEUE_NAME].qsize() > 0:
                logger.info(
                    "Camera config dict queue has items - updating cameras configs"
                )
                camera_config_dictionary = queues[CAMERA_CONFIG_DICT_QUEUE_NAME].get()

                for camera_id, camera in cameras_dictionary.items():
                    camera.update_config(camera_config_dictionary[camera_id])

            if start_event.is_set():
                # This tight loop ends up 100% the process, so a sleep between framecaptures is
                # necessary. We can get away with this because we don't expect another frame for
                # awhile.
                sleep(0.001)
                for camera in cameras_dictionary.values():
                    if camera.new_frame_ready:
                        try:
                            queue = queues[camera.camera_id]
                            latest_frame = camera.latest_frame
                            shared_memory_image_dictionary[camera.camera_id][:] = latest_frame.image.ravel()
                            latest_frame.image = None
                            queue.put(camera.latest_frame)


                        except Exception as e:
                            logger.exception(
                                f"Problem when putting a frame into the queue: Camera {camera.camera_id} - {e}"
                            )
                            break

        # close cameras on exit
        for camera in cameras_dictionary.values():
            logger.info(f"Closing camera {camera.camera_id}")
            camera.close()

    def check_if_camera_is_ready(self, cam_id: str):
        return self._cameras_ready_event_dictionary[cam_id].is_set()

    def _get_queue_by_camera_id(self, camera_id: str) -> multiprocessing.Queue:
        return self._queues[camera_id]

    def get_latest_frame_by_camera_id(self, camera_id) -> Union[FramePayload, None]:
        try:
            if camera_id not in self._queues:
                return

            queue = self._get_queue_by_camera_id(camera_id)
            if not queue.empty():
                frame_payload = queue.get(block=True)
                shared_memory_array = self._shared_memory_image_dictionary[camera_id][:]
                shared_image = np.asarray(shared_memory_array,
                                                 dtype='uint8').reshape(frame_payload.image_shape)
                frame_payload.image = shared_image


                return frame_payload
            else:
                return
        except Exception as e:
            logger.exception(f"Problem when grabbing a frame from: Camera {camera_id} - {e}")

    def get_queue_size_by_camera_id(self, camera_id: str) -> int:
        return self._queues[camera_id].qsize()

    def update_camera_configs(self, camera_config_dictionary):
        self._queues[CAMERA_CONFIG_DICT_QUEUE_NAME].put(camera_config_dictionary)

    def _create_shared_memory_image_dictionary(self, camera_config_dict: Dict[str, CameraConfig]):
        return {
            camera_id: multiprocessing.Array("I",
                                             camera_config_dict[camera_id].resolution_width *
                                             camera_config_dict[camera_id].resolution_height *
                                             3,  # color channels,
                                             )

            for camera_id in self._camera_ids
        }


if __name__ == "__main__":
    p = CamGroupSharedMemoryProcess(
        [
            "0",
        ]
    )
    p.start_capture()
    while True:
        # print("Queue size: ", p.queue_size("0"))
        curr = perf_counter_ns() * 1e-6
        frames = p.get_current_frame_by_camera_id("0")
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
