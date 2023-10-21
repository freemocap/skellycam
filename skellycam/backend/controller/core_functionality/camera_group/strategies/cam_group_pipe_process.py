import multiprocessing
import time
from multiprocessing import Process
from time import sleep
from typing import Dict, List, Any, Optional

from setproctitle import setproctitle

from skellycam import logger
from skellycam.backend.controller.core_functionality.opencv.camera.camera import Camera
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class CamGroupPipeProcess:
    def __init__(self, camera_configs: Dict[CameraId, CameraConfig]):
        if len(camera_configs) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")
        self._camera_configs = camera_configs
        self._is_capturing_events_by_camera = {camera_id: multiprocessing.Event() for camera_id in self.camera_ids}
        self._process: Optional[Process] = None
        self._payload = None
        self._is_capturing = False
        self._create_pipes()
        self._camera_config_queue = multiprocessing.Queue()

    @property
    def name(self):
        return self._process.name

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self._camera_configs.keys())

    @property
    def is_capturing(self):
        for event in self._is_capturing_events_by_camera.values():
            if not event.is_set():
                return False
        return True

    def start_capture(
            self,
            event_dictionary: Dict[str, multiprocessing.Event],
    ):
        """
        Start capturing frames. Only return if the underlying process is fully running.
        :return:
        """

        logger.info(f"Starting capture `Process` for {self.camera_ids}")

        event_dictionary["is_capturing_events_by_camera"] = self._is_capturing_events_by_camera

        self._process = Process(
            name=f"Cameras {self.camera_ids}",
            target=CamGroupPipeProcess._begin,
            args=(self._camera_configs,
                  self._pipe_sender_connections,
                  self._camera_config_queue,
                  event_dictionary),
        )
        self._process.start()
        while not self.is_capturing:
            logger.debug(f"Waiting for Process {self._process.name} cameras to start")
            sleep(0.25)

    def update_camera_configs(self, camera_config_dictionary):
        self._camera_config_queue.put(camera_config_dictionary)

    def check_if_camera_is_ready(self, cam_id: str):
        return self._is_capturing_events_by_camera[cam_id].is_set()

    def get_new_frames_by_camera_id(self, camera_id) -> List[FramePayload]:
        new_frames = []
        try:
            if camera_id not in self._pipe_receiver_connections:
                raise ValueError(f"Camera {camera_id} not in pipes: {self._pipe_receiver_connections.keys()}")

            pipe_connection = self._pipe_receiver_connections[camera_id]

            while pipe_connection.poll():
                frame_bytes = pipe_connection.recv_bytes()
                new_frames.append(FramePayload.from_bytes(frame_bytes))

        except Exception as e:
            logger.error(f"Problem when grabbing a frame from: Camera {camera_id} - {e}")
            logger.exception(e)
            raise e
        return new_frames

    def _create_pipes(self):
        self._pipes = {camera_id: multiprocessing.Pipe(duplex=True) for camera_id in self.camera_ids}
        self._pipe_receiver_connections = {
            camera_id: pipe[0] for camera_id, pipe in self._pipes.items()
        }
        self._pipe_sender_connections = {
            camera_id: pipe[1] for camera_id, pipe in self._pipes.items()
        }

    @staticmethod
    def _create_cameras(camera_configs: Dict[CameraId, CameraConfig],
                        pipe_connections  # multiprocessing.connection.Connection
                        ) -> Dict[str, Camera]:
        cameras = {
            camera_id: Camera(config=camera_config,
                              pipe=pipe_connections[camera_id])
            for camera_id, camera_config in camera_configs.items()
        }
        return cameras

    @staticmethod
    def _begin(
            camera_configs: Dict[CameraId, CameraConfig],
            pipe_connections: Dict[str, Any],  # multiprocessing.connection.Connection
            camera_config_queue: multiprocessing.Queue,
            event_dictionary: Dict[str, multiprocessing.Event],
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_configs.keys()}"
        )
        is_capturing_events_by_camera = event_dictionary["is_capturing_events_by_camera"]
        all_cameras_ready_event = event_dictionary["all_cameras_ready"]
        close_cameras_event = event_dictionary["close_cameras"]

        process_name = f"Cameras {camera_configs.keys()}"
        setproctitle(process_name)

        cameras = CamGroupPipeProcess._create_cameras(
            camera_configs=camera_configs,
            pipe_connections=pipe_connections,
        )

        for camera in cameras.values():
            camera.connect(is_capturing_event=is_capturing_events_by_camera[camera.camera_id],
                           all_cameras_ready=all_cameras_ready_event)

        while not close_cameras_event.is_set():
            time.sleep(0.5)  # check for new configs every 0.5 seconds
            if camera_config_queue.qsize() > 0:
                logger.info(
                    "Camera config dict queue has items - updating cameras configs"
                )
                camera_config_dictionary = camera_config_queue.get()

                for camera_id, camera in cameras.items():
                    camera.update_config(camera_config_dictionary[camera_id])


        # close cameras on exit
        for camera in cameras.values():
            logger.info(f"Closing camera {camera.camera_id}")
            camera.close()



