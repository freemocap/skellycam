import logging
import math
import multiprocessing
import time
from multiprocessing import Process
from multiprocessing.connection import Connection
from time import perf_counter_ns, sleep
from typing import Dict, List, Union

from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.data_sharing_strategies.utilities.pipe_communicator import PipeCommunicator
from skellycam.opencv.group.strategies.data_sharing_strategies.utilities.queue_communicator import QueueCommunicator

logger = logging.getLogger(__name__)

CAMERA_CONFIG_DICT_PIPE_NAME = "incoming_camera_config_dict_pipe"


class CamGroupPipeProcess:
    def __init__(self, camera_ids: List[str]):

        if len(camera_ids) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._cameras_ready_event_dictionary = None
        self._camera_ids = camera_ids
        self._process: Process = None

        pipe_name_list = self._camera_ids.copy()
        pipe_name_list.append(CAMERA_CONFIG_DICT_PIPE_NAME)

        pipe_communicator = PipeCommunicator(identifiers=pipe_name_list)
        self._pipes = pipe_communicator.pipes

        self._camera_pipe_connections = {camera_id: pipe[0] for camera_id, pipe in self._pipes.items()} #send these to camera processes
        self._local_pipe_connections = {camera_id: pipe[1] for camera_id, pipe in self._pipes.items()} #use these from outside of the process (i.e. `self._begin`)

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


        self._process = Process(
            name=f"Cameras {self._camera_ids}",
            target=CamGroupPipeProcess._begin,
            args=(self._camera_ids,
                  self._camera_pipe_connections,
                  event_dictionary,
                  camera_config_dict),
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
            camera_pipe_connections: Dict[str, Connection],
            event_dictionary: Dict[str, multiprocessing.Event],
            camera_config_dict: Dict[str, CameraConfig],
    ):
        logger.info(
            f"Starting frame loop capture for cameras: {cam_ids}"
        )
        ready_event_dictionary = event_dictionary["ready"]
        start_event = event_dictionary["start"]
        exit_event = event_dictionary["exit"]

        setproctitle(f"Cameras {cam_ids}")

        process_camera_config_dict = {
            camera_id: camera_config_dict[camera_id] for camera_id in cam_ids
        }
        cameras_dictionary = CamGroupPipeProcess._create_cams(
            camera_config_dict=process_camera_config_dict
        )

        for camera in cameras_dictionary.values():
            camera.connect(ready_event_dictionary[camera.camera_id])

        frame_grabbed_time = time.perf_counter()

        while not exit_event.is_set():
            if not multiprocessing.parent_process().is_alive():
                logger.info(
                    f"Parent process is no longer alive. Exiting {cam_ids} process"
                )
                break


            if camera_pipe_connections[CAMERA_CONFIG_DICT_PIPE_NAME].poll():
                logger.info(
                    "Camera config dict queue has items - updating cameras configs"
                )
                camera_config_dictionary = camera_pipe_connections[CAMERA_CONFIG_DICT_PIPE_NAME].recv()

                for camera_id, camera in cameras_dictionary.items():
                    camera.update_config(camera_config_dictionary[camera_id])


            if start_event.is_set():
                # This tight loop ends up 100% the process, so a sleep between framecaptures is
                # necessary. We can get away with this because we don't expect another frame for
                # awhile.
                sleep(0.001)
                for camera in cameras_dictionary.values():
                    print(f"hello 0 - {camera.camera_id}")
                    if camera.new_frame_ready:
                        print(f"hello 1 - {camera.camera_id}")
                        frame_grabbed_time = time.perf_counter()
                        try:
                            logger.debug(f"Putting frame into pipe for Camera {camera.camera_id}")
                            camera_pipe_connection = camera_pipe_connections[camera.camera_id]
                            camera_pipe_connection.send(camera.latest_frame)
                            print(f"hello 2 - {camera.camera_id}")
                            #TODO - this might be faster if we send the image data as a byte array using `send_bytes` (but I'm not sure...)

                        except Exception as e:
                            logger.exception(
                                f"Problem when putting a frame into the queue: Camera {camera.camera_id} - {e}"
                            )
                            break
                    else:
                        logger.debug(f"No new frame from Camera {camera.camera_id} in {time.perf_counter() - frame_grabbed_time} seconds")

            else:
                logger.debug(f"Waiting for start event for cameras {cam_ids}")
                sleep(.1)

        # close cameras on exit
        for camera in cameras_dictionary.values():
            logger.info(f"Closing camera {camera.camera_id}")
            camera.close()

    def check_if_camera_is_ready(self, cam_id: str):
        return self._cameras_ready_event_dictionary[cam_id].is_set()



    def get_latest_frame_by_camera_id(self, camera_id) -> Union[FramePayload, None]:
        try:
            if camera_id not in self._camera_ids:
                logger.debug(f"Camera {camera_id} is not in this camera group")
                return

            pipe_connections = self._local_pipe_connections[camera_id]

            if pipe_connections.poll():
                logger.debug(f"Camera {camera_id} sent a frame!")
                received_item = pipe_connections.recv()
                if isinstance(received_item, FramePayload):
                    return received_item
                else:
                    logger.info(f"Received item from pipe is not a FramePayload: {received_item}")
                    raise Exception(f"Received item from pipe is not a FramePayload: {received_item}")

            # logger.debug(f"Camera {camera_id} did not send anything")
        except Exception as e:
            logger.exception(f"Problem when grabbing a frame from: Camera {camera_id} - {e}")
            return



    def update_camera_configs(self, camera_config_dictionary):
        logger.info("Sending camera config dictionary to process")
        self._local_pipe_connections[CAMERA_CONFIG_DICT_PIPE_NAME].send(camera_config_dictionary)


if __name__ == "__main__":
    p = CamGroupPipeProcess(
        [
            "0",
        ]
    )
    p.start_capture()
    while True:
        # print("Queue size: ", p.queue_size("0"))
        curr = perf_counter_ns() * 1e-6
        frames = p.get_latest_frame_by_camera_id("0")
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
