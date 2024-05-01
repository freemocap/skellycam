import logging
import multiprocessing
import time
from multiprocessing import Process
from typing import Dict, List, Any, Optional

from setproctitle import setproctitle

from skellycam.backend.core.camera.camera import (
    Camera,
)
from skellycam.backend.core.camera.config.camera_config import CameraConfig
from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.device_detection.image_rotation_types import RotationTypes
from skellycam.backend.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class CamSubarrayPipeProcess:
    def __init__(
            self,
            subarray_camera_configs: Dict[CameraId, CameraConfig],
    ):
        if len(subarray_camera_configs) == 0:
            raise ValueError("CamGroupProcess must have at least one camera")

        self._subarray_camera_configs = subarray_camera_configs

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

    def start_capture(self):
        """
        Start capturing frames. Only return if the underlying process is fully running.
        :return:
        """

        logger.info(f"Starting capture `Process` for {self.camera_ids}")

        self._process = Process(
            name=f"Cameras {self.camera_ids}",
            target=CamSubarrayPipeProcess._run_process,
            args=(
                self._subarray_camera_configs,
                self._pipe_sender_connections,
                self._camera_config_queue,
            ),
        )
        self._process.start()

    def update_camera_configs(
            self, camera_config_dictionary: Dict[CameraId, CameraConfig]
    ):
        for camera_id, camera_config in camera_config_dictionary.items():
            self._subarray_camera_configs[camera_id] = camera_config
        self._camera_config_queue.put(camera_config_dictionary)

    def get_new_frames_by_camera_id(self, camera_id) -> List[FramePayload]:
        new_frames = []
        try:
            if camera_id not in self._pipe_receiver_connections:
                raise ValueError(
                    f"Camera {camera_id} not in pipes: {self._pipe_receiver_connections.keys()}"
                )

            pipe_receiver_connection = self._pipe_receiver_connections[camera_id]

            while pipe_receiver_connection.poll():
                # logger.trace(f"Camera {camera_id} has a new frame!")
                frame_bytes = pipe_receiver_connection.recv_bytes()
                new_frames.append(FramePayload.from_bytes(frame_bytes))

            if len(new_frames) > 0:
                self._apply_image_rotation(new_frames)

        except Exception as e:
            logger.error(
                f"Problem when grabbing a frame from: Camera {camera_id} - {e}"
            )
            logger.exception(e)
            raise e
        return new_frames

    def _apply_image_rotation(self, new_frames: List[FramePayload]):
        for frame in new_frames:
            config = self._subarray_camera_configs[str(frame.camera_id)]
            if config.rotation != RotationTypes.NO_ROTATION:
                frame.rotate(config.rotation.to_opencv_constant())

    def _create_pipes(self):
        self._pipe_receiver_connections = {}
        self._pipe_sender_connections = {}
        for camera_id in self.camera_ids:
            receiver_connection, sender_connection = multiprocessing.Pipe(duplex=False)
            self._pipe_receiver_connections[camera_id] = receiver_connection
            self._pipe_sender_connections[camera_id] = sender_connection

    @staticmethod
    def _create_cameras(
            camera_configs: Dict[CameraId, CameraConfig],
            pipe_sender_connections,  # multiprocessing.connection.Connection
    ) -> Dict[CameraId, Camera]:
        cameras = {
            camera_id: Camera(
                config=camera_config,
                pipe_sender_connection=pipe_sender_connections[camera_id],
            )
            for camera_id, camera_config in camera_configs.items()
        }
        return cameras

    @staticmethod
    def _run_process(
            camera_configs: Dict[CameraId, CameraConfig],
            pipe_connections: Dict[str, Any],  # multiprocessing.connection.Connection
            camera_config_queue: multiprocessing.Queue,
    ):
        logger.debug(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_configs.keys()}"
        )

        process_name = f"Cameras {camera_configs.keys()}"
        setproctitle(process_name)

        cameras = CamSubarrayPipeProcess._create_cameras(
            camera_configs=camera_configs,
            pipe_sender_connections=pipe_connections,
        )

        for camera in cameras.values():
            logger.debug(f"Connecting to camera {camera.camera_id}")
            camera.connect()

        while True:
            # logger.trace(f"CamGroupProcess {process_name} is checking for new configs")
            time.sleep(1.0)  # check for new configs every so often
            if camera_config_queue.qsize() > 0:
                logger.info(
                    "Camera config dict queue has items - updating cameras configs"
                )
                camera_configs = camera_config_queue.get()
                if camera_configs is None:
                    logger.info("Received None - closing cameras")
                    break

                for camera_id, camera in cameras.items():
                    camera.update_config(camera_configs[camera_id])

        for camera in cameras.values():
            logger.debug(f"Closing camera {camera.camera_id}")
            camera.close()

        logger.debug(f"CamGroupProcess {process_name} is complete")
