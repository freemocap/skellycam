import asyncio
import logging
import multiprocessing
import time
from typing import Coroutine, Callable, Optional

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.frames.frontend_image_payload import FrontendImagePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.frames.shared_image_memory import SharedImageMemoryManager
from skellycam.core.recorder.video_recorder_manager import VideoRecorderProcessManager

logger = logging.getLogger(__name__)


class FrameWrangler:
    def __init__(self ):
        super().__init__()
        self._camera_configs: CameraConfigs = {}
        self._shared_memory_manager: Optional[SharedImageMemoryManager] = None
        self._ws_send_bytes: Optional[Callable[[bytes], Coroutine]] = None
        self._multi_frame_payload: Optional[MultiFramePayload] = None

        self._frame_output_pipe, self._frame_input_pipe = multiprocessing.Pipe(duplex=False)
        self._setup_recorder()

    def _setup_recorder(self):
        self._is_recording = False
        self._recorder_queue = multiprocessing.Queue()
        self._video_recorder_manager = VideoRecorderProcessManager(
            multi_frame_queue=self._recorder_queue,
        )

    def get_frame_input_pipe(self):
        return self._frame_input_pipe

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._ws_send_bytes = ws_send_bytes
        logger.trace(f"Websocket bytes sender function set")

    def set_camera_configs(self, camera_configs: CameraConfigs, shared_memory_manager: SharedImageMemoryManager):
        self._shared_memory_manager = shared_memory_manager
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
            if self._frame_output_pipe.poll():
                payload = self._frame_output_pipe.recv()
                logger.loop(f"Frame Wrangler - Received multi-frame payload: {payload}")
                await self._handle_payload(payload)
            await asyncio.sleep(0.001)

    async def _handle_payload(self, payload: MultiFramePayload):
        logger.loop(f"FrameWrangler - Hydrating shared memory images")
        payload.hydrate_shared_memory_images(self._shared_memory_manager)
        if self._is_recording:
            logger.loop(f"Sending payload to recorder with {len(payload.frames)} frames")
            self._recorder_queue.put(payload)

        if self._ws_send_bytes is not None:
            await self._send_frontend_payload(payload)


    async def _send_frontend_payload(self, payload: MultiFramePayload):
        if self._ws_send_bytes is None:
            raise ValueError("Websocket `send bytes` function not set!")

        logger.loop(f"FrameWrangler - Convert multi-frame payload to frontend payload")
        frontend_payload = FrontendImagePayload.from_multi_frame_payload(
            multi_frame_payload=payload
        )
        logger.loop(f"FrameWrangler - Sending frontend payload: {frontend_payload}")
        await self._ws_send_bytes(frontend_payload.to_msgpack())
