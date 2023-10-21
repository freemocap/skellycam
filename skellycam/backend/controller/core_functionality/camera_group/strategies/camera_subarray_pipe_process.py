import multiprocessing
import time
from multiprocessing import Process
from typing import Dict, List, Any, Optional

from setproctitle import setproctitle

from skellycam import logger
from skellycam.backend.controller.core_functionality.opencv.camera.camera import Camera
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class CamSubarrayPipeProcess:
    def __init__(self, subarray_camera_configs: Dict[CameraId, CameraConfig]):
        if len(subarray_camera_configs) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")
        self._subarray_camera_configs = subarray_camera_configs
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
        return list(self._subarray_camera_configs.keys())

    @property
    def any_capturing(self):
        for event in self._is_capturing_events_by_camera.values():
            if not event.is_set():
                return False
        return True

    @property
    def all_capturing(self):
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
            target=CamSubarrayPipeProcess._run_process,
            args=(self._subarray_camera_configs,
                  self._pipe_sender_connections,
                  self._camera_config_queue,
                  event_dictionary),
        )
        self._process.start()


    def update_camera_configs(self, camera_config_dictionary):
        self._camera_config_queue.put(camera_config_dictionary)

    def check_if_camera_is_ready(self, cam_id: str):
        return self._is_capturing_events_by_camera[cam_id].is_set()

    def get_new_frames_by_camera_id(self, camera_id) -> List[FramePayload]:
        new_frames = []
        try:
            if camera_id not in self._pipe_receiver_connections:
                raise ValueError(f"Camera {camera_id} not in pipes: {self._pipe_receiver_connections.keys()}")

            pipe_receiver_connection = self._pipe_receiver_connections[camera_id]

            while pipe_receiver_connection.poll():
                logger.trace(f"Camera {camera_id} has a new frame!")
                frame_bytes = pipe_receiver_connection.recv_bytes()
                new_frames.append(FramePayload.from_bytes(frame_bytes))

        except Exception as e:
            logger.error(f"Problem when grabbing a frame from: Camera {camera_id} - {e}")
            logger.exception(e)
            raise e
        return new_frames

    def _create_pipes(self):
        self._pipe_receiver_connections = {}
        self._pipe_sender_connections = {}
        for camera_id in self.camera_ids:
            receiver_connection, sender_connection = multiprocessing.Pipe(duplex=False)
            self._pipe_receiver_connections[camera_id] = receiver_connection
            self._pipe_sender_connections[camera_id] = sender_connection

    @staticmethod
    def _create_cameras(camera_configs: Dict[CameraId, CameraConfig],
                        pipe_sender_connections,  # multiprocessing.connection.Connection
                        event_dictionary: Dict[str, multiprocessing.Event],
                        ) -> Dict[str, Camera]:
        cameras = {
            camera_id: Camera(config=camera_config,
                              pipe_sender_connection=pipe_sender_connections[camera_id],
                              is_capturing_event=event_dictionary["is_capturing_events_by_camera"][camera_id],
                              all_cameras_ready=event_dictionary["all_cameras_ready"],
                              close_cameras_event=event_dictionary["close_cameras"],
                              )
            for camera_id, camera_config in camera_configs.items()
        }
        return cameras

    @staticmethod
    def _run_process(
            camera_configs: Dict[CameraId, CameraConfig],
            pipe_connections: Dict[str, Any],  # multiprocessing.connection.Connection
            camera_config_queue: multiprocessing.Queue,
            event_dictionary: Dict[str, multiprocessing.Event],
    ):
        logger.debug(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_configs.keys()}"
        )

        process_name = f"Cameras {camera_configs.keys()}"
        setproctitle(process_name)

        cameras = CamSubarrayPipeProcess._create_cameras(
            camera_configs=camera_configs,
            pipe_sender_connections=pipe_connections,
            event_dictionary=event_dictionary,
        )

        for camera in cameras.values():
            camera.connect()

        while not event_dictionary["close_cameras"].is_set():
            # logger.trace(f"CamGroupProcess {process_name} is checking for new configs")
            time.sleep(1.0)  # check for new configs every 0.5 seconds
            if camera_config_queue.qsize() > 0:
                logger.info(
                    "Camera config dict queue has items - updating cameras configs"
                )
                camera_config_dictionary = camera_config_queue.get()

                for camera_id, camera in cameras.items():
                    camera.update_config(camera_config_dictionary[camera_id])
