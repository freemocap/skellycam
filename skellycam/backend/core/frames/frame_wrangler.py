import logging
import multiprocessing
import time
from copy import deepcopy
from typing import List, Coroutine, Callable, Optional

from skellycam.backend.core.cameras.config.camera_config import CameraConfigs
from skellycam.backend.core.frames.frame_payload import FramePayload
from skellycam.backend.core.frames.frontend_image_payload import FrontendImagePayload
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.backend.core.video_recorder.video_recorder_manager import VideoRecorderProcessManager

logger = logging.getLogger(__name__)


class FrameWrangler:
    def __init__(
            self,
    ):
        super().__init__()
        self._camera_configs: CameraConfigs = {}
        self._multi_frame_recorder_queue = multiprocessing.Queue()
        self._video_recorder_manager = VideoRecorderProcessManager(
            multi_frame_queue=self._multi_frame_recorder_queue,
        )
        self._ws_send_bytes: Optional[Callable[[bytes], Coroutine]] = None
        self._is_recording = False

        self._current_multi_frame_payload = None
        self._previous_multi_frame_payload = None

    def set_ws_send_bytes(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._ws_send_bytes = ws_send_bytes

    def set_camera_configs(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._current_multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )

    @property
    def is_recording(self):
        return self._is_recording

    @property
    def prescribed_framerate(self):
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras to determine frame rate from!")

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

    def stop(self):
        logger.debug(f"Stopping incoming frame wrangler loop...")
        if self.is_recording:
            self.stop_recording()

    def start_recording(self, recording_folder_path: str):
        if len(self._camera_configs) == 0:
            raise ValueError("No cameras to record from!")

        logger.debug(f"Starting recording...")

        self._video_recorder_manager.start_recording(
            camera_configs=self._camera_configs,
            start_time_perf_counter_ns_to_unix_mapping=(
                time.perf_counter_ns(),
                time.time_ns(),
            ),
            recording_folder_path=recording_folder_path,
        )
        self._is_recording = True

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._is_recording = False
        self._video_recorder_manager.stop_recording()

    async def handle_new_frames(self, new_frames: List[FramePayload]):
        for frame in new_frames:
            self._current_multi_frame_payload.add_frame(frame=frame)

            if self._previous_multi_frame_payload is None and not self._current_multi_frame_payload.full:
                # wait until we have a full frame to copy from the first go-around
                continue

            if self._frame_timeout or self._current_multi_frame_payload.full:
                await self._handle_full_or_timeout()

    async def _handle_full_or_timeout(self):
        if self._previous_multi_frame_payload is None:
            if self._current_multi_frame_payload.full:
                self._previous_multi_frame_payload = deepcopy(self._current_multi_frame_payload)
            else:
                raise ValueError(
                    "Current multi-frame payload is not full, but there is no previous payload to backfill from")

        self._backfill_missing_with_previous_frame()
        self._multi_frame_recorder_queue.put(self._current_multi_frame_payload)
        await self._send_frontend_payload()
        self._previous_multi_frame_payload = deepcopy(self._current_multi_frame_payload)
        self._current_multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )

    async def _send_frontend_payload(self):
        if self._ws_send_bytes is None:
            raise ValueError("Websocket `send bytes` function not set!")
        frontend_payload = FrontendImagePayload.from_multi_frame_payload(
            multi_frame_payload=self._current_multi_frame_payload
        )
        await self._ws_send_bytes(frontend_payload.to_msgpack())

    def _frame_timeout(self) -> bool:
        time_since_oldest_frame_sec = (
                                                  time.perf_counter_ns() - self._current_multi_frame_payload.oldest_timestamp_ns) / 1e9
        return time_since_oldest_frame_sec > self.ideal_frame_duration

    def _backfill_missing_with_previous_frame(self):
        if self._current_multi_frame_payload.full:
            return

        for camera_id in self._previous_multi_frame_payload.camera_ids:
            if self._current_multi_frame_payload.frames[camera_id] is None:
                self._current_multi_frame_payload.add_frame(
                    frame=self._previous_multi_frame_payload.frames[camera_id]
                )
