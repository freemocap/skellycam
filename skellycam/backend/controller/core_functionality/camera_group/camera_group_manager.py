import multiprocessing
import threading
import time
from typing import Dict, Optional, List

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group import CameraGroup
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frames.frame_payload import FramePayload
from skellycam.models.cameras.frames.frontend import FrontendMultiFramePayload


class CameraGroupManager:

    def __init__(self,
                 frontend_frame_queue: multiprocessing.Queue, ) -> None:
        self.frontend_frame_queue = frontend_frame_queue
        self._camera_group: Optional[CameraGroup] = None
        self._camera_group_thread: Optional[threading.Thread] = None

        self._camera_configs: Optional[Dict[str, CameraConfig]] = None

    def _create_camera_group(self):
        self._camera_group = CameraGroup(camera_configs=self._camera_configs)
        self._camera_group_thread = threading.Thread(target=self._run_camera_group_loop, )

    def _run_camera_group_loop(self):
        self._camera_group.start()
        frontend_payload = FrontendMultiFramePayload(frames={})
        while not self._camera_group.exit_event.is_set():
            time.sleep(0.001)
            new_frames = self._camera_group.new_frames()
            if new_frames:
                self._handle_new_frames(frontend_payload, new_frames)

    def _handle_new_frames(self,
                           frontend_payload: FrontendMultiFramePayload,
                           new_frames:List[FramePayload]) -> FrontendMultiFramePayload:
        for frame in new_frames:
            frontend_payload.add_frame(frame=frame)
            if frontend_payload.full:
                self.frontend_frame_queue.put(frontend_payload)
                frontend_payload = FrontendMultiFramePayload(frames={})
        return frontend_payload

    def start(self, camera_configs: Dict[str, CameraConfig]):
        logger.debug(f"Starting camera group thread...")
        self._camera_configs = camera_configs
        self._create_camera_group()
        self._camera_group_thread.start()

    def stop_camera_group(self):
        logger.debug(f"Stopping camera group thread...")
        self._camera_group.close()
        self._camera_group_thread.join()

    def update_configs(self, camera_configs: Dict[str, CameraConfig]):
        logger.debug(f"Updating camera configs to {camera_configs.keys()}")
        self._camera_group.update_configs(camera_configs=camera_configs)
