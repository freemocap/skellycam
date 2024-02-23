import logging
import threading
import time
from typing import Dict, Optional, Union

from skellycam.backend.controller.core_functionality.camera_group.camera_group import (
    CameraGroup,
)
from skellycam.backend.controller.core_functionality.camera_group.incoming_frame_wrangler import (
    IncomingFrameWrangler,
)
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.models.cameras.frames.frame_payload import (
    MultiFramePayload,
)

logger = logging.getLogger(__name__)


class CameraGroupManager(threading.Thread):
    def __init__(self, camera_configs: CameraConfigs) -> None:
        super().__init__()
        self.daemon = True
        self._camera_configs = camera_configs
        self._camera_group = CameraGroup(camera_configs=self._camera_configs)
        self._camera_runner_thread: Optional[threading.Thread] = None

        self._incoming_frame_wrangler: IncomingFrameWrangler = IncomingFrameWrangler(
            camera_configs=self._camera_configs
        )

        self._is_recording = False
        self._stop_recording = False

    @property
    def camera_configs(self) -> CameraConfigs:
        return self._camera_configs

    @property
    def new_frontend_payload_available(self) -> bool:
        return self._incoming_frame_wrangler.new_frontend_payload_available

    @property
    def is_recording(self) -> bool:
        if self._is_recording and self._video_recorder_manager is None:
            logger.error(f"Video recorder manager not initialized")
            raise AssertionError(
                "Video recorder manager not initialized but `_is_recording` is True"
            )
        return self._is_recording

    def start_recording(self):
        logger.debug(f"Starting recording...")
        self._incoming_frame_wrangler.start_recording()
        self._is_recording = True

    def get_latest_frames(self) -> MultiFramePayload:
        return self._incoming_frame_wrangler.latest_frontend_payload

    def run(self):
        self._camera_group.start()
        multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )
        while self._camera_group.any_capturing:
            new_frames = self._camera_group.get_new_frames()
            if len(new_frames) > 0:
                multi_frame_payload = self._incoming_frame_wrangler.handle_new_frames(
                    multi_frame_payload, new_frames
                )
            elif self.is_recording:
                if self._video_recorder_manager.has_frames_to_save:
                    self._video_recorder_manager.one_frame_to_disk()
                else:
                    if self._stop_recording:
                        logger.debug(
                            f"No more frames to save, and `_stop_recording` is True - closing video recorder manager"
                        )
                        self._close_video_recorder_manager()
            else:
                time.sleep(0.001)

    def _close_video_recorder_manager(self):
        self._video_recorder_manager.finish_and_close()
        self._video_recorder_manager = None
        self._is_recording = False

    def close(self):
        logger.debug(f"Stopping camera group thread...")

        self._camera_group.close()
        # self._video_recorder_manager.finish_and_close()
        self._camera_runner_thread.join()

    def update_camera_configs(self, camera_configs: CameraConfigs):
        logger.debug(f"Updating camera configs to \n{camera_configs}")
        self._camera_configs = camera_configs
        self._camera_group.update_configs(camera_configs=camera_configs)
