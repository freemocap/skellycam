import logging
import multiprocessing
from multiprocessing import Process
from typing import Optional

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.cameras.trigger_camera.camera_trigger_loop import camera_trigger_loop
from skellycam.core.detection.camera_id import CameraId

logger = logging.getLogger(__name__)


class MultiCameraTriggerProcess:
    def __init__(
            self,
            camera_configs: CameraConfigs,
            frame_pipe,  # send-only pipe connection
            shared_memory_name: str
    ):
        self._camera_configs = camera_configs
        self._frame_pipe = frame_pipe
        self._update_pipe_receiver, self._update_pipe_sender = multiprocessing.Pipe(duplex=False)
        self._shared_memory_name = shared_memory_name
        self._number_of_frames: Optional[int] = None
        self._process: Optional[Process] = None

        self._exit_event = multiprocessing.Event()

    def _create_process(self):
        self._process = Process(
            name="MultiCameraTriggerProcess",
            target=MultiCameraTriggerProcess._run_process,
            args=(self._camera_configs,
                  self._frame_pipe,
                  self._update_pipe_receiver,
                  self._shared_memory_name,
                  self._exit_event,
                  self._number_of_frames,
                  )
        )

    @property
    def camera_ids(self) -> [CameraId]:
        return [CameraId(camera_id) for camera_id in self._camera_configs.keys()]

    def start(self, number_of_frames: Optional[int] = None):
        logger.debug("Stating CameraTriggerProcess...")
        self._number_of_frames = number_of_frames
        self._create_process()
        self._process.start()

    def update_configs(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._update_pipe_sender.put(camera_configs)

    async def close(self):
        logger.debug("Closing CameraTriggerProcess...")
        self._exit_event.set()
        self._process.join()
        logger.debug("CameraTriggerProcess closed")

    @staticmethod
    def _run_process(camera_configs: CameraConfigs,
                     frame_pipe,  # send-only pipe connection
                     update_pipe,  # receive-only pipe connection
                     shared_memory_name: str,
                     exit_event: multiprocessing.Event,
                     number_of_frames: Optional[int] = None
                     ):
        logger.debug(f"CameraTriggerProcess started")

        camera_trigger_loop(camera_configs=camera_configs,
                            multi_frame_pipe=frame_pipe,
                            config_update_pipe=update_pipe,
                            shared_memory_name=shared_memory_name,
                            number_of_frames=number_of_frames,
                            exit_event=exit_event)

        logger.debug(f"CameraTriggerProcess completed")
