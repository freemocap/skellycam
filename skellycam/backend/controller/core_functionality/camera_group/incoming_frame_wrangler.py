import logging
import time
from typing import Optional, List

import cv2

from skellycam.backend.controller.core_functionality.camera_group.video_recorder.video_recorder_manager import (
    VideoRecorderManager,
)
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.frames.frame_payload import (
    MultiFramePayload,
    FramePayload,
)

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

    @property
    def frames_to_save(self):
        return self._video_recorder_manager.has_frames_to_save

    @property
    def is_recording(self):
        return self._is_recording

    def handle_new_frames(
        self, multi_frame_payload: MultiFramePayload, new_frames: List[FramePayload]
    ) -> MultiFramePayload:
        for frame in new_frames:
            multi_frame_payload.add_frame(frame=frame)
            if multi_frame_payload.full:
                if self._is_recording:
                    self._record_multi_frame(multi_frame_payload)

                frontend_payload = self._prepare_frontend_payload(
                    multi_frame_payload=multi_frame_payload
                )
                self.set_new_frontend_payload(frontend_payload=frontend_payload)
                multi_frame_payload = MultiFramePayload.create(
                    camera_ids=list(self._camera_configs.keys())
                )
        return multi_frame_payload

    def _record_multi_frame(self, multi_frame_payload):
        if self._video_recorder_manager is None:
            logger.error(f"Video recorder manager not initialized")
            raise AssertionError(
                "Video recorder manager not initialized but `_is_recording` is True"
            )
        self._video_recorder_manager.handle_multi_frame_payload(
            multi_frame_payload=multi_frame_payload
        )

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

    def start_recording(self, recording_folder_path: str):
        logger.debug(f"Starting recording...")

        self._video_recorder_manager.start_recording(
            start_time_perf_counter_ns_to_unix_mapping=(
                time.perf_counter_ns(),
                time.time_ns(),
            ),
            recording_folder_path=recording_folder_path,
        )
        self._is_recording = True

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        if self._video_recorder_manager is None:
            raise AssertionError(
                "Video recorder manager isn't initialized, but `StopRecordingInteraction` was called! This shouldn't happen..."
            )
        self._is_recording = False
        self._video_recorder_manager.stop_recording()

    def save_one_frame_to_disk(self):
        if self._video_recorder_manager is None:
            raise AssertionError(
                "Video recorder manager isn't initialized, but `SaveOneFrameInteraction` was called! This shouldn't happen..."
            )
        self._video_recorder_manager.one_frame_to_disk()
