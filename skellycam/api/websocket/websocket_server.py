import asyncio
import json
import logging
import time
from collections import deque

import numpy as np
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect
from fastapi import FastAPI

from skellylogs import LogRecordModel, LogLevels
from skellylogs.handlers.websocket_log_queue_handler import get_websocket_log_queue

from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
from skellycam.utilities.wait_functions import await_10ms
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt, MultiframeTimestampFloat

logger = logging.getLogger(__name__)

BACKPRESSURE_WARNING_THRESHOLD: int = 1000  # Number of frames before we warn about backpressure


class ServerFramerateCalculator:
    """Compute true camera capture framerate from (frame_number, capture_timestamp_ns) pairs.

    frame_number increments by 1 for every camera capture at the hardware level.
    capture_timestamp_ns is perf_counter_ns at the moment of camera grab.
    When the websocket skips frames due to backpressure, frame_number jumps
    but we can still compute the true per-frame duration from the gap.
    """

    def __init__(self, source_name: str, max_observations: int = 200):
        self._source_name: str = source_name
        self._observations: deque[tuple[int, float]] = deque(maxlen=max_observations)
        self._per_frame_durations_ms: deque[float] = deque(maxlen=1000)

    def update(self, frame_number: int, capture_timestamp_ns: float) -> None:
        if self._observations:
            prev_fn, prev_ts = self._observations[-1]
            frame_delta = frame_number - prev_fn
            if frame_delta > 0:
                per_frame_ns = (capture_timestamp_ns - prev_ts) / frame_delta
                per_frame_ms = per_frame_ns / 1e6
                # Record one duration entry per actual frame captured
                for _ in range(frame_delta):
                    self._per_frame_durations_ms.append(per_frame_ms)
        self._observations.append((frame_number, capture_timestamp_ns))

    @property
    def current_framerate(self) -> CurrentFramerate | None:
        if len(self._per_frame_durations_ms) < 2:
            return None
        durations = np.array(self._per_frame_durations_ms)
        return CurrentFramerate.from_durations_ms(
            durations_ms=durations,
            framerate_source=self._source_name,
        )

    def clear(self) -> None:
        """Reset accumulated durations. The next update() will begin a fresh interval."""
        self._observations.clear()
        self._per_frame_durations_ms.clear()


class WebsocketServer:
    def __init__(self, app: FastAPI, websocket: WebSocket):
        self.websocket = websocket
        self.global_kill_flag = app.state.global_kill_flag
        self._cgm: CameraGroupManager = get_or_create_camera_group_manager(app=app)

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self.last_received_frontend_confirmation: int = -1

        self.last_sent_frame_number: int = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None
        self._server_framerate_calculators: dict[CameraGroupIdString, ServerFramerateCalculator] = {}
        self._display_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._last_framerate_send_time: float = 0.0

        # Serialize all websocket sends — the `websockets` library does not
        # support concurrent writes on the same connection. Without this lock,
        # two tasks calling send_json/send_bytes at the same time hit an
        # internal `assert waiter is None or waiter.cancelled()` in the
        # protocol drain logic.
        self._send_lock = asyncio.Lock()

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
        # Cancel all tasks
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()
        logger.debug("WebsocketRunner context manager exited.")

    @property
    def should_continue(self) -> bool:
        return (
            not self.global_kill_flag.value
            and self._websocket_should_continue
            and self.websocket.client_state == WebSocketState.CONNECTED
        )

    def _signal_shutdown(self) -> None:
        """Signal all tasks to stop and cancel them."""
        self._websocket_should_continue = False
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()

    async def _send_json(self, data: dict) -> None:
        """Send JSON through the websocket, serialized by the send lock."""
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(data)

    async def _send_bytes(self, data: bytes) -> None:
        """Send bytes through the websocket, serialized by the send lock."""
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_bytes(data)

    async def _send_text(self, data: str) -> None:
        """Send text through the websocket, serialized by the send lock."""
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(data)

    async def run(self):
        logger.info("Starting websocket runner...")
        self.ws_tasks = [
            asyncio.create_task(self._frontend_image_relay(), name="WebsocketFrontendImageRelay"),
            asyncio.create_task(self._logs_relay(), name="WebsocketLogsRelay"),
            asyncio.create_task(self._client_message_handler(), name="WebsocketClientMessageHandler"),
            asyncio.create_task(self._app_state_sender(), name="WebsocketStateSender"),
        ]

        try:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.debug("Websocket runner cancelled")
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            raise
        finally:
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()

    def check_frame_acknowledgment_status(self) -> bool:
        if self.last_sent_frame_number == -1:
            return True
        return self.last_received_frontend_confirmation >= self.last_sent_frame_number

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info("Starting frontend image payload relay...")
        try:
            skipped_previous = False
            while self.should_continue:
                await await_10ms()
                if self.check_frame_acknowledgment_status():
                    if skipped_previous:  # skip an extra frame if there was backpressure from frontend
                        skipped_previous = False
                    else:
                        new_frontend_payloads: dict[
                            CameraGroupIdString, tuple[
                                FrameNumberInt, MultiframeTimestampFloat, bytes]] = self._cgm.get_latest_frontend_payloads(
                            if_newer_than=self.last_sent_frame_number,
                            display_image_sizes=self._display_image_sizes)

                        for camera_group_id, (frame_number,
                                              multiframe_timestamp,
                                              payload_bytes) in new_frontend_payloads.items():
                            await self._send_bytes(payload_bytes)
                            self.last_sent_frame_number = frame_number

                            # Server framerate: computed from frame_number + capture timestamp.
                            # frame_number increments by 1 per actual camera capture,
                            # multiframe_timestamp is perf_counter_ns at the camera grab.
                            # This gives the true capture rate even when frames are
                            # skipped in the websocket relay due to backpressure.
                            if camera_group_id not in self._server_framerate_calculators:
                                self._server_framerate_calculators[camera_group_id] = ServerFramerateCalculator(
                                    source_name="Server")
                            self._server_framerate_calculators[camera_group_id].update(
                                frame_number=frame_number,
                                capture_timestamp_ns=multiframe_timestamp,
                            )

                            # Display framerate: websocket send rate (what the UI actually receives)
                            if camera_group_id not in self._display_framerate_trackers:
                                self._display_framerate_trackers[camera_group_id] = FramerateTracker.create(
                                    framerate_source="Display")
                            self._display_framerate_trackers[camera_group_id].update(time.perf_counter_ns())
                else:
                    skipped_previous = True
                    backpressure = self.last_sent_frame_number - self.last_received_frontend_confirmation
                    if backpressure > BACKPRESSURE_WARNING_THRESHOLD and backpressure % BACKPRESSURE_WARNING_THRESHOLD == 0:
                        logger.trace(
                            f"Backpressure detected: {backpressure} frames not acknowledged by frontend! "
                            f"Last sent frame: {self.last_sent_frame_number}, "
                            f"last received confirmation: {self.last_received_frontend_confirmation}")

                # Send framerate updates from our local trackers (throttled to ~1Hz)
                now = time.monotonic()
                if now - self._last_framerate_send_time >= 0.25:
                    for camera_group_id, server_calc in self._server_framerate_calculators.items():
                        if camera_group_id not in self._display_framerate_trackers:
                            continue
                        server_framerate = server_calc.current_framerate
                        display_tracker = self._display_framerate_trackers[camera_group_id]
                        if server_framerate and display_tracker.has_data:
                            framerate_message = {
                                "message_type": "framerate_update",
                                "camera_group_id": camera_group_id,
                                "backend_framerate": server_framerate.model_dump(),
                                "frontend_framerate": display_tracker.current_framerate.model_dump()
                            }
                            await self._send_json(framerate_message)
                            # Reset both trackers so the next report reflects only
                            # the interval since this report.
                            server_calc.clear()
                            display_tracker.clear()
                    self._last_framerate_send_time = now

        except (WebSocketDisconnect, AssertionError):
            logger.info("Client disconnected, ending frontend image relay task...")
        except RuntimeError as e:
            if "close" in str(e).lower():
                logger.info("Websocket closed during image relay send, ending task...")
            else:
                raise
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()

    async def _logs_relay(self, ws_log_level: int = LogLevels.TRACE.value):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if not logs_queue.empty():
                    log_record: LogRecordModel = LogRecordModel(**logs_queue.get_nowait())
                    if log_record.levelno < ws_log_level:
                        continue
                    log_data = log_record.model_dump()
                    await self._send_json(log_data)
                else:
                    await await_10ms()
        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")
        except (WebSocketDisconnect, AssertionError):
            logger.info("Client disconnected, ending log relay task...")
        except RuntimeError as e:
            if "close" in str(e).lower():
                logger.info("Websocket closed during log relay send, ending task...")
            else:
                raise
        except Exception as e:
            logger.exception(f"Error in websocket log relay: {e.__class__}: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()

    async def _app_state_sender(self):
        """
        Periodically send the application state to the frontend.
        """
        logger.info("Starting state sender task...")
        previous_state: dict | None = None
        try:
            while self.should_continue:
                state_dict = self._cgm.to_state_dict()
                if previous_state is None or state_dict != previous_state:
                    state_message = {
                        "message_type": "app_state",
                        "state": state_dict
                    }
                    await self._send_json(state_message)
                await asyncio.sleep(1.0)
                previous_state = state_dict
        except asyncio.CancelledError:
            logger.debug("State sender task cancelled")
        except (WebSocketDisconnect, AssertionError):
            logger.info("Client disconnected, ending state sender task...")
        except RuntimeError as e:
            if "close" in str(e).lower():
                logger.info("Websocket closed during state send, ending task...")
            else:
                raise
        except Exception as e:
            logger.exception(f"Error in state sender: {e.__class__}: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()
            logger.info("Ending state sender task...")

    async def _client_message_handler(self):
        """
        Handle messages from the client. Acts as the disconnect sentinel —
        when the client disconnects, this task signals all other tasks to stop.
        """
        logger.info("Starting client message handler...")
        try:
            while self.should_continue:
                message = await self.websocket.receive()

                message_type: str = message.get("type", "")

                # ASGI disconnect message — client is gone
                if message_type == "websocket.disconnect":
                    logger.info(f"Client disconnected (code={message.get('code', 'unknown')}), shutting down websocket tasks...")
                    self._signal_shutdown()
                    return

                if "text" in message:
                    text_content: str = message["text"]
                    if text_content.strip().startswith('{') or text_content.strip().startswith('['):
                        try:
                            data = json.loads(text_content)
                            if 'frameNumber' in data:
                                self.last_received_frontend_confirmation = data['frameNumber']
                                self._display_image_sizes = data.get('displayImageSizes', None)
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Failed to decode JSON from client websocket message: {e}") from e
                    else:
                        if text_content.strip() == "ping":
                            await self._send_text("pong")
                        elif text_content.strip() == "pong":
                            pass
                        else:
                            logger.info(f"Websocket received message: `{text_content}`")
                elif "bytes" in message:
                    logger.trace(f"Received binary websocket message ({len(message['bytes'])} bytes)")
                else:
                    raise RuntimeError(f"Unexpected ASGI websocket message: {message}")

        except WebSocketDisconnect:
            logger.info("Client disconnected (WebSocketDisconnect), shutting down websocket tasks...")
        except asyncio.CancelledError:
            logger.debug("Client message handler task cancelled")
        except Exception as e:
            logger.exception(f"Error handling client message: {e.__class__}: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()
            logger.info("Ending client message handler...")
