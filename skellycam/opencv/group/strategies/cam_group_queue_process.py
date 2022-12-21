import logging
import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import Dict, List, Union

from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.queue_communicator import QueueCommunicator

logger = logging.getLogger(__name__)

CAMERA_CONFIG_DICT_QUEUE_NAME = "camera_config_dict_queue"


class CamGroupProcess:
    def __init__(self, cam_ids: List[str]):
        self._cameras_ready_event_dictionary = None
        self._cam_ids = cam_ids
        self._process: Process = None
        self._payload = None
        queue_name_list = self._cam_ids.copy()
        queue_name_list.append(CAMERA_CONFIG_DICT_QUEUE_NAME)
        communicator = QueueCommunicator(queue_name_list)
        self._queues = communicator.queues

    @property
    def camera_ids(self):
        return self._cam_ids

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
        logger.info(f"Starting capture `Process` for {self._cam_ids}")

        self._cameras_ready_event_dictionary = {
            camera_id: multiprocessing.Event() for camera_id in self._cam_ids
        }
        event_dictionary["ready"] = self._cameras_ready_event_dictionary

        self._process = Process(
            name=f"Cameras {self._cam_ids}",
            target=CamGroupProcess._begin,
            args=(self._cam_ids, self._queues, event_dictionary, camera_config_dict),
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
        cameras_dictionary = CamGroupProcess._create_cams(
            camera_config_dict=process_camera_config_dict
        )

        for camera in cameras_dictionary.values():
            camera.connect(ready_event_dictionary[camera.camera_id])

        while not exit_event.is_set():
            # This tight loop ends up 100% the process, so a sleep between framecaptures is
            # necessary. We can get away with this because we don't expect another frame for
            # awhile.
            if queues[CAMERA_CONFIG_DICT_QUEUE_NAME].qsize() > 0:
                logger.info(
                    "Camera config dict queue has items - updating cameras configs"
                )
                camera_config_dictionary = queues[CAMERA_CONFIG_DICT_QUEUE_NAME].get()

                for camera_id, camera in cameras_dictionary.items():
                    camera.update_config(camera_config_dictionary[camera_id])

            if start_event.is_set():
                sleep(0.001)
                for camera in cameras_dictionary.values():
                    if camera.new_frame_ready:
                        queue = queues[camera.camera_id]
                        queue.put(camera.latest_frame)

        # close cameras on exit
        for camera in cameras_dictionary.values():
            logger.info(f"Closing camera {camera.camera_id}")
            camera.close()

    def check_if_camera_is_ready(self, cam_id: str):
        return self._cameras_ready_event_dictionary[cam_id].is_set()

    def get_by_cam_id(self, cam_id) -> Union[FramePayload, None]:
        if cam_id not in self._queues:
            return

        queue = self._queues[cam_id]
        if not queue.empty():
            return queue.get(block=True)

    def update_camera_configs(self, camera_config_dictionary):
        self._queues[CAMERA_CONFIG_DICT_QUEUE_NAME].put(camera_config_dictionary)


if __name__ == "__main__":
    p = CamGroupProcess(
        [
            "0",
        ]
    )
    p.start_capture()
    while True:
        # print("Queue size: ", p.queue_size("0"))
        curr = perf_counter_ns() * 1e-6
        frames = p.get_by_cam_id("0")
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
