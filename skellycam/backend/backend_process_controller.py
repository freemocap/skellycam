import logging
import multiprocessing
import time
from typing import List, Union

from skellycam.backend.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


class BackendController:
    def __init__(self,
                 pipe_connection,
                 exit_event: multiprocessing.Event):
        self._pipe_connection = pipe_connection
        self._exit_event = exit_event

    def start_camera_group_process(self, camera_ids: List[int]):
        process = multiprocessing.Process(target=self._run_camera_group_process,
                                          args=(camera_ids,
                                                self._pipe_connection,
                                                self._exit_event))
        process.start()
        while not self._exit_event.is_set():
            time.sleep(0.1)
            if self._pipe_connection.poll():
                message = self._pipe_connection.recv()
                logger.debug(f"Received message from frontend process: {message}")
                if message == "stop":
                    process.terminate()
                    process.join()
                    self._exit_event.set()
                    logger.info("Backend process terminated")
                    break
                else:
                    logger.error(f"Unknown message received from frontend process: {message}")
                    raise ValueError(f"Unknown message received from frontend process: {message}")

    @staticmethod
    def _run_camera_group_process(camera_ids: List[int],
                                  pipe_connection,
                                  exit_event: multiprocessing.Event):
        camera_group = create_camera_group(camera_ids)
        pipe_connection.send({"type": "camera_group_created",
                              "camera_config_dictionary": camera_group.camera_config_dictionary})
        camera_group.start()
        should_continue = True
        logger.info("Emitting `cameras_connected_signal`")
        pipe_connection.send({"type": "cameras_connected"})

        while camera_group.is_capturing and should_continue and not exit_event.is_set():
            if pipe_connection.poll():
                message = pipe_connection.recv()
                logger.debug(f"Received message from frontend process: {message}")
                if message == "stop":
                    camera_group.close()
                    logger.info("Backend process terminated")
                    should_continue = False
                    exit_event.set()
                    break

            frame_payload_dictionary = camera_group.latest_frames()
            pipe_connection.send({"type": "new_images",
                                  "frames_payload": frame_payload_dictionary})


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
