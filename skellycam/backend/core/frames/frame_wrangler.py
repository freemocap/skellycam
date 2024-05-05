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
        self._recorder_queue = multiprocessing.Queue()
        self._sender_pipe, self._receiver_pipe = multiprocessing.Pipe(duplex=False)
        self._video_recorder_manager = VideoRecorderProcessManager(
            multi_frame_queue=self._recorder_queue,
        )
        self._ws_send_bytes: Optional[Callable[[bytes], Coroutine]] = None
        self._is_recording = False

        self._multi_frame_payload: Optional[MultiFramePayload] = None
        self._previous_multi_frame_payload: Optional[MultiFramePayload] = None

    def get_frame_pipe(self):
        return self._receiver_pipe

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._ws_send_bytes = ws_send_bytes

    def set_camera_configs(self, camera_configs: CameraConfigs):
        self._camera_configs = camera_configs
        self._multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )

    @property
    def is_recording(self):
        return self._is_recording

    def close(self):
        logger.debug(f"Closing frame wrangler...")
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

    async def listen_for_frames(self):
        while True:
            if self._receiver_pipe.poll():
                payload_bytes = self._sender_pipe.recv()
                payload = MultiFramePayload.from_msgpack(payload_bytes)
                logger.trace(f"Received multi-frame payload: {payload}")
                await self._handle_payload(payload)

    async def _handle_payload(self, payload: MultiFramePayload):
        if self._is_recording:
            payload.log("before_put_in_recorder_queue")
            self._recorder_queue.put(payload)

        if self._ws_send_bytes is not None:
            logger.trace(f"Sending multi-frame payload to frontend: {payload}")
            await self._send_frontend_payload()

        self._previous_multi_frame_payload = deepcopy(self._multi_frame_payload)
        self._multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys())
        )

    async def _send_frontend_payload(self):
        if self._ws_send_bytes is None:
            raise ValueError("Websocket `send bytes` function not set!")
        frontend_payload = FrontendImagePayload.from_multi_frame_payload(
            multi_frame_payload=self._multi_frame_payload
        )
        await self._ws_send_bytes(frontend_payload.to_msgpack())

