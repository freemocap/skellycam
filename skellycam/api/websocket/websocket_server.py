import asyncio
import logging
import multiprocessing
import time

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellycam.core.camera_group.camera.config.camera_config import CameraConfig
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFramerate, FramerateTracker
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppStateDTO, SkellycamAppState, get_skellycam_app_state
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from skellycam.utilities.wait_functions import async_wait_1ms, async_wait_10ms

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, websocket: WebSocket):

        self.websocket = websocket
        self._app_state: SkellycamAppState = get_skellycam_app_state()

        self.latest_backend_framerate: CurrentFramerate | None = None
        self.latest_frontend_framerate: CurrentFramerate | None = None

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        self._websocket_should_continue = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        self._websocket_should_continue = False

        # Only close if still connected
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.close()

    @property
    def should_continue(self):
        return (
                self._app_state.ipc_flags.global_should_continue
                and self._websocket_should_continue
                and self.websocket.client_state == WebSocketState.CONNECTED
        )

    async def run(self):
        logger.info("Starting websocket runner...")
        self.ws_tasks = [asyncio.create_task(self._frontend_image_relay(), name="WebsocketFrontendImageRelay"),
                         asyncio.create_task(self._ipc_queue_relay(), name="WebsocketIPCQueueRelay"),
                         asyncio.create_task(self._logs_relay(), name="WebsocketLogsRelay"), ]

        try:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            raise
        finally:
            # Cancel all tasks when exiting
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()

    async def _ipc_queue_relay(self):
        """
        Relay messages from the sub-processes to the frontend via the websocket.
        """
        logger.info("Starting websocket relay listener...")

        try:
            while self.should_continue:
                if not self._app_state.ipc_queue.empty():
                    try:
                        await self._handle_ipc_queue_message(message=self._app_state.ipc_queue.get())
                    except multiprocessing.queues.Empty:
                        continue
                    except Exception as e:
                        logger.exception(f"Error handling IPC queue message: {e.__class__}: {e}")
                        raise
                else:
                    await async_wait_1ms()

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Ending listener for frontend payload messages in queue...")
        logger.info("Ending listener for client messages...")

    async def _handle_ipc_queue_message(self, message: object|None = None):
        if isinstance(message, CameraConfig):
            logger.trace(f"Updating device extracted camera config for camera {message.camera_id}")
            self._app_state.set_device_extracted_camera_config(message)

        elif isinstance(message, RecordingInfo):
            logger.trace(f"Relaying RecordingInfo to frontend")
        elif isinstance(message, CurrentFramerate):
            self.latest_backend_framerate = message

        else:
            raise ValueError(f"Unknown message type: {type(message)}")

        await self.websocket.send_json(message.model_dump())

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay...")
        frontend_framerate_tracker = FramerateTracker.create(framerate_source="frontend")
        camera_group_uuid = None
        latest_mf_number = -1
        try:
            while self.should_continue:
                await async_wait_1ms()

                if not self._app_state.frame_escape_shm:
                    latest_mf_number = -1
                    continue

                if self._app_state.camera_group and camera_group_uuid != self._app_state.camera_group.uuid:
                    latest_mf_number = -1
                    camera_group_uuid = self._app_state.camera_group.uuid
                    continue

                if not self._app_state.frame_escape_shm.latest_mf_number.value > latest_mf_number:
                    continue

                mf_payload = self._app_state.frame_escape_shm.get_multi_frame_payload(
                    camera_configs=self._app_state.camera_group.camera_configs,
                    retrieve_type="latest")
                frontend_framerate_tracker.update(time.perf_counter_ns())
                if mf_payload.multi_frame_number % 10 == 0:
                    # update every 10 multi-frames to match backend framerate behavior
                    self.latest_frontend_framerate = frontend_framerate_tracker.current
                await self._send_frontend_payload(mf_payload)
                latest_mf_number = mf_payload.multi_frame_number

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending Frontend Image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            raise

    async def _send_frontend_payload(self,
                                     mf_payload: MultiFramePayload):
        mf_payload.backend_framerate = self.latest_backend_framerate
        mf_payload.frontend_framerate = self.latest_frontend_framerate
        frontend_payload = FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf_payload)
        logger.loop(f"Sending frontend payload through websocket...")
        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket is not connected, cannot send payload!")
            raise RuntimeError("Websocket is not connected, cannot send payload!")

        if self.websocket.client_state != WebSocketState.CONNECTED:
            return

        await self.websocket.send_bytes(frontend_payload.model_dump_json().encode('utf-8'))

        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket shut down while sending payload!")
            raise RuntimeError("Websocket shut down while sending payload!")


    async def _logs_relay(self):
        logger.info("Starting websocket log relay listener...")
        websocket_log_queue = get_websocket_log_queue()

        try:
            while self.should_continue:
                if not websocket_log_queue.empty() or self.websocket.client_state != WebSocketState.CONNECTED:
                    try:
                        log_record = websocket_log_queue.get_nowait()
                        await self.websocket.send_json(log_record)
                    except (multiprocessing.queues.Empty, websocket_log_queue.Empty):
                        await async_wait_1ms()
                else:
                    await async_wait_10ms()

        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")