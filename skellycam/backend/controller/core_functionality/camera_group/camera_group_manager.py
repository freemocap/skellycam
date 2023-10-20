import threading
import time
from typing import Dict, Optional, List

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group import CameraGroup
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload, MultiFramePayload


class CameraGroupManager:

    def __init__(self,
                 frontend_frame_pipe_sender  # multiprocessing.connection.Connection
                 ) -> None:
        self.frontend_frame_pipe_sender = frontend_frame_pipe_sender
        self._camera_group: Optional[CameraGroup] = None
        self._camera_group_thread: Optional[threading.Thread] = None

        self._camera_configs: Optional[Dict[CameraId, CameraConfig]] = None

    def _create_camera_group(self):
        self._camera_group = CameraGroup(camera_configs=self._camera_configs)
        self._camera_group_thread = threading.Thread(target=self._run_camera_group_loop, )

    def _run_camera_group_loop(self):
        self._camera_group.start()
        multi_frame_payload = MultiFramePayload.create(camera_ids=list(self._camera_configs.keys()))
        while not self._camera_group.exit_event.is_set():
            time.sleep(0.001)
            new_frames = self._camera_group.new_frames()
            if new_frames:
                self._handle_new_frames(multi_frame_payload, new_frames)

    def _handle_new_frames(self,
                           multi_frame_payload: MultiFramePayload,
                           new_frames:List[FramePayload]) -> MultiFramePayload:
        for frame in new_frames:
            multi_frame_payload.add_frame(frame=frame)
            if multi_frame_payload.full:
                self.frontend_frame_pipe_sender.send_bytes(multi_frame_payload.to_bytes())
                multi_frame_payload = MultiFramePayload.create(camera_ids=list(self._camera_configs.keys()))
        return multi_frame_payload

    def start(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.debug(f"Starting camera group thread...")
        self._camera_configs = camera_configs
        self._create_camera_group()
        self._camera_group_thread.start()

    def stop_camera_group(self):
        logger.debug(f"Stopping camera group thread...")
        self._camera_group.close()
        self._camera_group_thread.join()

    def update_configs(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.debug(f"Updating camera configs to {camera_configs.keys()}")
        self._camera_group.update_configs(camera_configs=camera_configs)
