import threading
import time
from typing import Dict, Optional, List, Union

import cv2

from skellycam.backend.controller.core_functionality.camera_group.camera_group import (
    CameraGroup,
)
from skellycam.backend.controller.core_functionality.camera_group.video_recorder.video_recorder_manager import (
    VideoRecorderManager,
)
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.models.cameras.frames.frame_payload import (
    MultiFramePayload,
    FramePayload,
)
import logging

logger = logging.getLogger(__name__)


class IncomingFrameWrangler:
    def __init__(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._video_recorder_manager = VideoRecorderManager(
            camera_configs=self._camera_configs
        )

        self._latest_frontend_payload: Optional[MultiFramePayload] = None
        self.new_frontend_payload_available: bool = False
        self._is_recording = False

    def handle_new_frames(
        self, multi_frame_payload: MultiFramePayload, new_frames: List[FramePayload]
    ) -> MultiFramePayload:
        for frame in new_frames:
            multi_frame_payload.add_frame(frame=frame)
            if multi_frame_payload.full:
                if self._is_recording:
                    if self._video_recorder_manager is None:
                        logger.error(f"Video recorder manager not initialized")
                        raise AssertionError(
                            "Video recorder manager not initialized but `_is_recording` is True"
                        )
                    self._video_recorder_manager.handle_multi_frame_payload(
                        multi_frame_payload=multi_frame_payload
                    )

                frontend_payload = self._prepare_frontend_payload(
                    multi_frame_payload=multi_frame_payload
                )
                self.set_new_frontend_payload(frontend_payload=frontend_payload)
                multi_frame_payload = MultiFramePayload.create(
                    camera_ids=list(self._camera_configs.keys())
                )
        return multi_frame_payload

    def _prepare_frontend_payload(
        self, multi_frame_payload: MultiFramePayload, scale_images: float = 0.5
    ) -> MultiFramePayload:
        frontend_payload = multi_frame_payload.copy(deep=True)
        frontend_payload.resize(scale_factor=scale_images)
        for frame in frontend_payload.frames.values():
            frame.set_image(image=cv2.cvtColor(frame.get_image(), cv2.COLOR_BGR2RGB))
        return frontend_payload

    def set_new_frontend_payload(self, frontend_payload: MultiFramePayload):
        self._latest_frontend_payload = frontend_payload
        self.new_frontend_payload_available = True

    @property
    def latest_frontend_payload(self) -> MultiFramePayload:
        self.new_frontend_payload_available = False
        return self._latest_frontend_payload

    def wait_for_new_frontend_payload(
        self, wait_for_new: bool, max_wait_seconds: float
    ) -> Union[MultiFramePayload, bool]:
        max_wait_ns = max_wait_seconds * 1e9
        start_wait_time = time.perf_counter_ns()
        if wait_for_new:
            while not self.new_frontend_payload_available:
                time.sleep(0.0001)
                if time.perf_counter_ns() - start_wait_time >= max_wait_ns:
                    return False
        return self.latest_frontend_payload

    def start_recording(self):
        logger.debug(f"Starting recording...")
        if self._video_recorder_manager is not None:
            raise AssertionError("Video recorder manager already initialized! ")

        self._video_recorder_manager.start_recording(
            start_time_perf_counter_ns_to_unix_mapping=(
                time.perf_counter_ns(),
                time.time_ns(),
            )
        )
        self._is_recording = True
        self._stop_recording = False

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        if self._video_recorder_manager is None:
            raise AssertionError(
                "Video recorder manager isn't initialized, but `StopRecordingInteraction` was called! This shouldn't happen..."
            )
        self._video_recorder_manager.stop_recording()
        self._stop_recording = True


class CameraGroupManager(threading.Thread):
    def __init__(self, camera_configs: [Dict[CameraId, CameraConfig]]) -> None:
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

    def get_latest_frames(self) -> MultiFramePayload:
        return self._incoming_frame_wrangler.latest_frontend_payload

    def wait_for_new_frames(self) -> Union[MultiFramePayload, bool]:
        return self._incoming_frame_wrangler.wait_for_new_frontend_payload

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

    async def _close_video_recorder_manager(self):
        await self._video_recorder_manager.finish_and_close()
        self._video_recorder_manager = None
        self._is_recording = False

    # def start(self, camera_configs: Dict[CameraId, CameraConfig]):
    #     logger.debug(f"Starting camera group thread...")
    #     self._camera_configs = camera_configs
    #     self._camera_group = CameraGroup(camera_configs=self._camera_configs)
    #     self._camera_runner_thread = threading.Thread(
    #         target=self._run_camera_group_loop, daemon=True
    #     )
    #     self._camera_runner_thread.start()

    async def close(self):
        logger.debug(f"Stopping camera group thread...")

        await self._camera_group.close()
        # self._video_recorder_manager.finish_and_close()
        self._camera_runner_thread.join()

    def update_configs(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.debug(f"Updating camera configs to {camera_configs.keys()}")
        self._camera_configs = camera_configs
        self._camera_group.update_configs(camera_configs=camera_configs)

    @property
    def latest_frontend_payload(self) -> MultiFramePayload:
        self.new_frontend_payload_available = False
        return self._latest_frontend_payload

    @latest_frontend_payload.setter
    def latest_frontend_payload(self, new_frontend_payload: MultiFramePayload):
        self._latest_frontend_payload = new_frontend_payload
        self.new_frontend_payload_available = True
