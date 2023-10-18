import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import Dict, List, Union

from setproctitle import setproctitle

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.strategies.queue_communicator import QueueCommunicator
from skellycam.backend.controller.core_functionality.opencv.camera.camera import Camera
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.frame_payload import FramePayload

CAMERA_CONFIG_DICT_QUEUE_NAME = "camera_config_dict_queue"


class CamGroupQueueProcess:
    def __init__(self, camera_configs: Dict[str, CameraConfig]):

        if len(camera_configs) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._cameras_ready_event_dictionary = None
        self._camera_configs = camera_configs
        self._process: Process = None
        self._payload = None
        queue_name_list = list(self._camera_configs.keys())
        queue_name_list.append(CAMERA_CONFIG_DICT_QUEUE_NAME)
        communicator = QueueCommunicator(queue_name_list)
        self._queues = communicator.queues

    @property
    def camera_ids(self) -> List[str]:
        return list(self._camera_configs.keys())

    @property
    def name(self):
        return self._process.name

    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
    ):
        """
        Start capturing frames. Only return if the underlying process is fully running.
        :return:
        """

        logger.info(f"Starting capture `Process` for {self.camera_ids}")

        self._cameras_ready_event_dictionary = {
            camera_id: multiprocessing.Event()
            for camera_id in self.camera_ids
        }
        event_dictionary["ready"] = self._cameras_ready_event_dictionary

        self._process = Process(
            name=f"Cameras {self.camera_ids}",
            target=CamGroupQueueProcess._begin,
            args=(self._camera_configs, self._queues, event_dictionary),
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
    def _create_cams(camera_configs: Dict[str, CameraConfig]) -> Dict[str, Camera]:
        cam_dict = {
            camera_config.camera_id: Camera(camera_config)
            for camera_config in camera_configs.values()
        }
        return cam_dict

    @staticmethod
    def _begin(
            camera_configs: Dict[str, CameraConfig],
            queues: Dict[str, multiprocessing.Queue],
            event_dictionary: Dict[str, multiprocessing.Event],
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_configs.keys()}"
        )
        ready_event_dictionary = event_dictionary["ready"]
        start_event = event_dictionary["start"]
        exit_event = event_dictionary["exit"]

        process_name = f"Cameras {camera_configs.keys()}"
        setproctitle(process_name)

        cameras_dictionary = CamGroupQueueProcess._create_cams(
            camera_configs=camera_configs
        )

        for camera in cameras_dictionary.values():
            camera.connect(ready_event_dictionary[camera.camera_id])

        while not exit_event.is_set():
            if not multiprocessing.parent_process().is_alive():
                logger.info(
                    f"Parent process is no longer alive. Exiting process: {process_name}"
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
                        new_frame_added = True
                        try:
                            queues[camera.camera_id].put(camera.latest_frame)

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

    def get_current_frame_by_camera_id(self, camera_id) -> Union[FramePayload, None]:
        try:
            if camera_id not in self._queues:
                return

            queue = self._get_queue_by_camera_id(camera_id)
            if not queue.empty():
                return queue.get(block=True)
        except Exception as e:
            logger.exception(f"Problem when grabbing a frame from: Camera {camera_id} - {e}")
            return

    def get_queue_size_by_camera_id(self, camera_id: str) -> int:
        return self._queues[camera_id].qsize()

    def update_camera_configs(self, camera_config_dictionary):
        self._queues[CAMERA_CONFIG_DICT_QUEUE_NAME].put(camera_config_dictionary)

