import logging
import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import Dict, List

from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CamGroupProcess:
    def __init__(self,
                 camera_ids: List[str],
                 frame_lists_by_camera: Dict[str, List[FramePayload]],
                 camera_config_queues: Dict[str, multiprocessing.Queue],
                 ):

        self._camera_ids = camera_ids
        assert all([camera_id in frame_lists_by_camera.keys() for camera_id in
                    self._camera_ids]), "We should only have frame lists for cameras in this group"
        assert all([camera_id in camera_config_queues.keys() for camera_id in
                    self._camera_ids]), "We should only have configs for cameras in this group"

        self._frame_lists_by_camera = frame_lists_by_camera
        self._camera_config_queues = camera_config_queues

        if len(camera_ids) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._cameras_ready_event_dictionary = None
        self._process: Process = None
        self._payload = None

    @property
    def camera_ids(self):
        return self._camera_ids

    @property
    def name(self):
        return self._process.name

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
                  self._frame_lists_by_camera,
                  event_dictionary,
                  self._camera_config_queues,
                  ),
        )
        self._process.start()
        while not self._process.is_alive():
            logger.debug(f"Waiting for Process {self._process.name} to start")
            sleep(0.25)

    @staticmethod
    def _create_cameras(camera_configs: Dict[str, CameraConfig]) -> Dict[str, Camera]:
        cameras = {}
        for camera_config in camera_configs.values():
            if camera_config.use_this_camera:
                cameras[camera_config.camera_id] = Camera(camera_config)
        return cameras

    @staticmethod
    def _begin(
            camera_ids: List[str],
            frame_lists_by_camera: Dict[str, List[FramePayload]],
            event_dictionary: Dict[str, multiprocessing.Event],
            camera_config_queues: Dict[str, multiprocessing.Queue],
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_ids}"
        )
        ready_event_dictionary = event_dictionary["ready"]
        start_event = event_dictionary["start"]
        exit_event = event_dictionary["exit"]
        should_record_frames_event = event_dictionary["should_record_frames"]

        setproctitle(f"Cameras {camera_ids}")

        current_camera_configs = {camera_id: camera_config_queues[camera_id].get() for camera_id in camera_ids}
        cameras_dictionary = CamGroupProcess._create_cameras(
            camera_configs=current_camera_configs
        )

        for camera in cameras_dictionary.values():
            camera.connect(ready_event_dictionary[camera.camera_id])

        number_of_recorded_frames = {camera_id: 0 for camera_id in camera_ids}

        while not exit_event.is_set():
            if not multiprocessing.parent_process().is_alive():
                logger.info(
                    f"Parent process is no longer alive. Exiting {camera_ids} process"
                )
                break

            if start_event.is_set():
                # This tight loop ends up 100% the process, so a sleep between framecaptures is
                # necessary. We can get away with this because we don't expect another frame for
                # awhile.
                sleep(0.001)

                current_camera_configs = CamGroupProcess._check_for_new_camera_configs(
                    cameras_dictionary=cameras_dictionary,
                    camera_config_queues=camera_config_queues,
                    current_camera_configs=current_camera_configs
                )

                for camera in cameras_dictionary.values():
                    if camera.new_frame_ready:
                        try:
                            latest_frame = camera.latest_frame
                            latest_frame.current_chunk_size = len(frame_lists_by_camera[camera.camera_id])
                            latest_frame.number_of_frames_recorded = number_of_recorded_frames[camera.camera_id]

                            # latest_frames[camera.camera_id]= latest_frame   # where the displayed images come from

                            if should_record_frames_event.is_set():
                                number_of_recorded_frames[camera.camera_id] += 1
                                frame_lists_by_camera[camera.camera_id].append(
                                    latest_frame)  # will be saved to video files
                            else:
                                if len(frame_lists_by_camera[camera.camera_id]) == 0:
                                    # TODO - I don't understand why the frame lists show up empty after initialized with
                                    #  a blank FramePayload.
                                    #  Need to figure this out someday, but this hack works so.. yay tech debt lol

                                    logger.debug(
                                        f"Camera {camera.camera_id} frame list is empty - appending this frame")
                                    frame_lists_by_camera[camera.camera_id].append(latest_frame)

                                frame_lists_by_camera[camera.camera_id][0] = latest_frame

                                number_of_recorded_frames = {camera_id: 0 for camera_id in camera_ids}

                        except Exception as e:
                            logger.exception(
                                f"Problem when saving a frame from Camera {camera.camera_id} - {e}"
                            )
                            break

        # close cameras on exit
        for camera in cameras_dictionary.values():
            logger.info(f"Closing camera {camera.camera_id}")
            camera.close()

    def check_if_camera_is_ready(self, cam_id: str):
        return self._cameras_ready_event_dictionary[cam_id].is_set()

    @staticmethod
    def _check_for_new_camera_configs(cameras_dictionary: Dict[str, Camera],
                                      camera_config_queues: Dict[str, multiprocessing.Queue],
                                      current_camera_configs: Dict[str, CameraConfig] = None):
        for camera_id, queue in camera_config_queues.items():
            if not queue.empty():
                new_config = queue.get()
                if current_camera_configs[camera_id] != new_config:
                    logger.info(
                        f"Received new config for camera {camera_id}: {new_config}, Old config: {current_camera_configs[camera_id]}")
                    cameras_dictionary[camera_id].update_config(camera_config=new_config)
                    current_camera_configs[camera_id] = new_config

        return current_camera_configs


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
