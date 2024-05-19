import asyncio
import logging
import time
from typing import Coroutine, Callable, Optional

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.frames.frontend_image_payload import FrontendImagePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.memory.camera_shared_memory_manager import CameraSharedMemoryManager

logger = logging.getLogger(__name__)


class FrameWrangler:
    def __init__(self):
        super().__init__()
        self._camera_configs: Optional[CameraConfigs] = None
        self._shared_memory_manager: Optional[CameraSharedMemoryManager] = None
        self._ws_send_bytes: Optional[Callable[[bytes], Coroutine]] = None
        self._multi_frame_payload: Optional[MultiFramePayload] = None
        self._setup_recorder()

        self._listener_task: Optional[asyncio.Task] = None
        self._should_continue_listening = True

    @property
    def multi_frames_received(self):
        if not self._multi_frame_payload:
            return 0
        return self._multi_frame_payload.multi_frame_number + 1

    def _setup_recorder(self):
        self._is_recording = False
        # self._video_recorder_manager = VideoRecorderProcessManager()

    def set_websocket_bytes_sender(self, ws_send_bytes: Callable[[bytes], Coroutine]):
        self._ws_send_bytes = ws_send_bytes
        logger.trace(f"Set websocket bytes sender function")

    def set_camera_configs(self, camera_configs: CameraConfigs,
                           shared_memory_manager: CameraSharedMemoryManager):
        self._shared_memory_manager = shared_memory_manager
        self._camera_configs = camera_configs
        self._multi_frame_payload = MultiFramePayload.create(
            camera_ids=list(self._camera_configs.keys()),
            multi_frame_number=-1
        )

    @property
    def is_recording(self):
        return self._is_recording

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

    def start_frame_listener(self):
        logger.debug(f"Starting frame listener...")
        self._listener_task = asyncio.create_task(self.listen_for_frames())

    async def listen_for_frames(self):
        try:
            while self._should_continue_listening or self._shared_memory_manager.new_multi_frame_payload_available():
                logger.loop(f"Awaiting multi-frame payload...")

                self._multi_frame_payload = await self._shared_memory_manager.get_multi_frame_payload(
                    payload=self._multi_frame_payload
                )

                logger.loop(f"Received multi-frame payload!\n {self._multi_frame_payload}")
                await self._handle_payload()
        except Exception as e:
            logger.error(f"Error in listen_for_frames: {type(e).__name__} - {e}")
            logger.exception(e)
        logger.trace(f"Stopped listening for multi-frames")

    async def _handle_payload(self):
        if self._is_recording:
            logger.loop(f"Sending payload to recorder with {len(self._multi_frame_payload.frames)} frames")
            self._recorder_queue.put(self._multi_frame_payload)

        if self._ws_send_bytes is not None:
            logger.info(f"Sending `self._multi_frame_payload` to frontend")
            await self._send_frontend_payload()

    async def _send_frontend_payload(self):
        if self._ws_send_bytes is None:
            raise ValueError("Websocket `send bytes` function not set!")

        logger.loop(f"FrameWrangler - Convert multi-frame payload to frontend payload")
        frontend_payload = FrontendImagePayload.from_multi_frame_payload(
            multi_frame_payload=self._multi_frame_payload,
        )
        logger.loop(f"FrameWrangler - Sending frontend payload: {frontend_payload}")
        await self._ws_send_bytes(frontend_payload.to_msgpack())

    async def close(self):
        logger.debug(f"Closing frame wrangler...")
        if self.is_recording:
            self.stop_recording()
        if self._listener_task is not None:
            self._should_continue_listening = False
            await self._listener_task
