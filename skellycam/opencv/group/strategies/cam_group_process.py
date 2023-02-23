import logging
import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import Dict, List, Union

from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CamGroupProcess:
    def __init__(self,
                 camera_ids: List[str],
                 latest_frames: Dict[str, FramePayload],
                 frame_dictionaries: Dict[str, Dict[str, Union[str, List[FramePayload]]]],
                 incoming_camera_configs: Dict[str, CameraConfig],
                 recording_frames: multiprocessing.Value,
                 ):
        self._latest_frames = latest_frames
        self._frame_dictionaries = frame_dictionaries
        self._incoming_camera_configs = incoming_camera_configs
        self._recording_frames = recording_frames

        if len(camera_ids) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._cameras_ready_event_dictionary = None
        self._camera_ids = camera_ids
        self._process: Process = None
        self._payload = None

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def name(self):
        return self._process.name

    @property
    def recording_frames(self) -> multiprocessing.Value:
        return self._recording_frames

    @property
    def is_capturing(self):
        if self._process:
            return self._process.is_alive()
        return False

    def terminate(self):
        if self._process:
            self._process.terminate()
            logger.info(f"CamGroupProcess {self.name} terminate command executed")

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
            target=CamGroupProcess._begin,
            args=(self._camera_ids,
                  self._frame_dictionaries,
                  self._latest_frames,
                  self._recording_frames,
                  event_dictionary,
                  camera_config_dict),
        )
        self._process.start()
        while not self._process.is_alive():
            logger.debug(f"Waiting for Process {self._process.name} to start")
            sleep(0.25)

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
            frame_list_by_camera: List[FramePayload],
            latest_frames: Dict[str, Union[FramePayload, None]],
            recording_frames: multiprocessing.Value,
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
            if not multiprocessing.parent_process().is_alive():
                logger.info(
                    f"Parent process is no longer alive. Exiting {cam_ids} process"
                )
                break

            # if queues[CAMERA_CONFIG_DICT_QUEUE_NAME].qsize() > 0:
            #     logger.info(
            #         "Camera config dict queue has items - updating cameras configs"
            #     )
            #     camera_config_dictionary = queues[CAMERA_CONFIG_DICT_QUEUE_NAME].get()
            # 
            #     for camera_id, camera in cameras_dictionary.items():
            #         camera.update_config(camera_config_dictionary[camera_id])

            if start_event.is_set():
                # This tight loop ends up 100% the process, so a sleep between framecaptures is
                # necessary. We can get away with this because we don't expect another frame for
                # awhile.
                sleep(0.001)
                for camera in cameras_dictionary.values():
                    if camera.new_frame_ready:
                        try:
                            latest_frame = camera.latest_frame
                            latest_frames[camera.camera_id] = latest_frame

                            if recording_frames.value:
                                frames_list = frame_list_by_camera[camera.camera_id]
                                frames_list.append(latest_frame)

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

    def update_camera_configs(self, camera_config_dictionary):
        for camera_id, camera_config in camera_config_dictionary.items():
            self._incoming_camera_configs[camera_id] = camera_config


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
        frames = p.get_latest_frame_by_camera("0")
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")
