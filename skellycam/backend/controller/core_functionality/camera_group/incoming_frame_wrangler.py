import logging
import multiprocessing
import time
from copy import deepcopy
from typing import Optional, List

import cv2

from skellycam.backend.controller.core_functionality.camera_group.video_recorder.video_recorder_manager import (
    VideoRecorderProcessManager,
)
from skellycam.backend.models.cameras.camera_configs import CameraConfigs
from skellycam.backend.models.cameras.frames.frame_payload import (
    FramePayload,
)
from skellycam.backend.models.cameras.frames.multi_frame_payload import (
    MultiFramePayload,
)

logger = logging.getLogger(__name__)


class IncomingFrameWrangler:
    def __init__(
        self,
        camera_configs: CameraConfigs,
    ):
        super().__init__()
        self._camera_configs = camera_configs
        self._multi_frame_queue = multiprocessing.Queue()
        self._video_recorder_manager = VideoRecorderProcessManager(
            camera_configs=self._camera_configs,
            multi_frame_queue=self._multi_frame_queue,
        )

        self._latest_frontend_payload: Optional[MultiFramePayload] = None
        self.new_frontend_payload_available: bool = False
        self._is_recording = False

        self._current_multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )
        self._previous_multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )

    @property
    def is_recording(self):
        return self._is_recording

    @property
    def prescribed_framerate(self):
        all_frame_rates = [
            camera_config.framerate for camera_config in self._camera_configs.values()
        ]
        if len(set(all_frame_rates)) > 1:
            logger.warning(
                f"Frame rates are not all the same: {all_frame_rates} - Defaulting to the slowest frame rate"
            )
        return min(all_frame_rates)

    @property
    def ideal_frame_duration(self):
        return 1 / self.prescribed_framerate

    @property
    def latest_frontend_payload(self) -> MultiFramePayload:
        self.new_frontend_payload_available = False
        return self._latest_frontend_payload

    def stop(self):
        logger.debug(f"Stopping incoming frame wrangler loop...")
        self._multi_frame_queue.put(None)

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

    def handle_new_frames(self, new_frames: List[FramePayload]):
        if not self._previous_multi_frame_payload.full:
            for frame in new_frames:
                self._previous_multi_frame_payload.add_frame(frame=frame)
                if not self._previous_multi_frame_payload.full:
                    return

        for frame in new_frames:
            self._current_multi_frame_payload.add_frame(frame=frame)

        self._yeet_if_ready()

    def _yeet_if_ready(self):
        time_since_oldest_frame = (
            time.perf_counter_ns()
            - self._current_multi_frame_payload.oldest_timestamp_ns
        ) / 1e9
        frame_timeout = time_since_oldest_frame > self.ideal_frame_duration

        if frame_timeout or self._current_multi_frame_payload.full:
            self._backfill_missing_with_previous_frame()
            self._set_new_frontend_payload()

            if self._is_recording:
                self._multi_frame_queue.put(self._current_multi_frame_payload)

            self._previous_multi_frame_payload = deepcopy(
                self._current_multi_frame_payload
            )
            self._current_multi_frame_payload = MultiFramePayload.create(
                camera_ids=list(self._camera_configs.keys())
            )

    def _backfill_missing_with_previous_frame(self):
        if self._current_multi_frame_payload.full:
            return

        for camera_id in self._previous_multi_frame_payload.camera_ids:
            if self._current_multi_frame_payload.frames[camera_id] is None:
                self._current_multi_frame_payload.add_frame(
                    frame=self._previous_multi_frame_payload.frames[camera_id]
                )

    def _prepare_frontend_payload(
        self,
        scaled_image_long_side: int = 640,
    ) -> MultiFramePayload:
        frontend_payload = self._current_multi_frame_payload.copy(deep=True)

        scale_factor = scaled_image_long_side / max(
            frontend_payload.frames[0].get_resolution()
        )

        frontend_payload.resize(scale_factor=scale_factor)
        for frame in frontend_payload.frames.values():
            frame.set_image(image=cv2.cvtColor(frame.get_image(), cv2.COLOR_BGR2RGB))
        return frontend_payload

    def _set_new_frontend_payload(self):
        self._latest_frontend_payload = self._prepare_frontend_payload()
        self.new_frontend_payload_available = True
