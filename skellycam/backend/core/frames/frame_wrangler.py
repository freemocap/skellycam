import logging
import multiprocessing
import time
from copy import deepcopy
from typing import Optional, List

import cv2
import msgpack
import numpy as np
from starlette.websockets import WebSocket

from skellycam.backend.core.camera.config.camera_config import CameraConfigs
from skellycam.backend.core.frames.frame_payload import FramePayload
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.backend.core.video_recorder.video_recorder_manager import VideoRecorderProcessManager

logger = logging.getLogger(__name__)


class CameraViewer:
    def __init__(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._windows = {}

    def start(self):
        for camera_id in self._camera_configs.keys():
            cv2.namedWindow(self._create_window_name(camera_id), cv2.WINDOW_NORMAL)

    def new_multi_frame(self, multi_frame_payload: MultiFramePayload):
        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is not None:
                cv2.imshow(self._create_window_name(camera_id), frame.get_image())
        # q to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            cv2.destroyAllWindows()
            self._windows = {}

    def _create_window_name(self, camera_id: str) -> str:
        return f"Camera {camera_id} - Press `Q` to quit"


class FrameWrangler:
    def __init__(
            self,
            camera_configs: CameraConfigs,
    ):
        super().__init__()
        self._websocket: Optional[WebSocket] = None
        self._camera_configs = camera_configs
        self._multi_frame_queue = multiprocessing.Queue()
        self._video_recorder_manager = VideoRecorderProcessManager(
            camera_configs=self._camera_configs,
            multi_frame_queue=self._multi_frame_queue,
        )
        self._camera_viewer = CameraViewer(camera_configs=self._camera_configs)

        self._latest_frontend_payload: Optional[MultiFramePayload] = None
        self.new_frontend_payload_available: bool = False
        self._is_recording = False
        self._show_camera_window = False

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

    def attach_websocket(self, websocket: WebSocket):
        self._websocket = websocket

    def stop(self):
        logger.debug(f"Stopping incoming frame wrangler loop...")
        if self.is_recording:
            self.stop_recording()
        self._multi_frame_queue.put(None)

    def start_camera_viewer(self):
        logger.debug(f"Starting camera viewer...")
        self._show_camera_window = True
        self._camera_viewer.start()

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

    async def handle_new_frames(self, new_frames: List[FramePayload]):
        if not self._previous_multi_frame_payload.full:
            for frame in new_frames:
                self._previous_multi_frame_payload.add_frame(frame=frame)
                if not self._previous_multi_frame_payload.full:
                    return

        for frame in new_frames:
            self._current_multi_frame_payload.add_frame(frame=frame)

        await self._yeet_if_ready()

    async def send_multi_frame_down_websocket(self, multi_frame_payload: MultiFramePayload):
        websocket_payload = {}
        for frame in multi_frame_payload.frames.values():
            image_jpg = await self.frame_to_jpg_bytes(frame)
            websocket_payload[frame.camera_id] = image_jpg

        # Use MessagePack to serialize the dictionary into binary data
        websocket_payload_bytes = msgpack.packb(websocket_payload, use_bin_type=True)

        # Send the binary data over the WebSocket
        await self._websocket.send_bytes(websocket_payload_bytes)

    async def frame_to_jpg_bytes(self, frame: FramePayload) -> bytes:
        image: np.ndarray = frame.get_image()
        success, image_jpg = cv2.imencode(".jpg", image)
        if not success:
            logger.error(f"Failed to encode image to jpg")
        else:
            logger.debug(
                f"Sending image to frontend of size {len(image_jpg.tobytes())} res {image.shape}...")
        return image_jpg.tobytes()

    async def _yeet_if_ready(self):
        time_since_oldest_frame = (
                                          time.perf_counter_ns()
                                          - self._current_multi_frame_payload.oldest_timestamp_ns
                                  ) / 1e9
        frame_timeout = time_since_oldest_frame > self.ideal_frame_duration

        if frame_timeout or self._current_multi_frame_payload.full:
            self._backfill_missing_with_previous_frame()
            # self._set_new_frontend_payload()
            if self._websocket is not None:
                await self.send_multi_frame_down_websocket(self._current_multi_frame_payload)
            if self._show_camera_window:
                self._camera_viewer.new_multi_frame(self._current_multi_frame_payload)
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

        if scaled_image_long_side is not None:
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
