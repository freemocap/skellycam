import asyncio
import logging
import time
from collections import deque
from typing import Callable, Awaitable

import numpy as np
from starlette.websockets import WebSocketDisconnect

from skellylogs import LogRecordModel, LogLevels
from skellylogs.handlers.websocket_log_queue_handler import get_websocket_log_queue

from skellycam.api.websocket.websocket_messages import (
    WebsocketFramerateUpdate,
    WebsocketAppState,
)
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.recorders.framerate_tracker import FramerateTracker, CurrentFramerate
from skellycam.core.types.type_overloads import CameraGroupIdString
from skellycam.utilities.wait_functions import await_10ms

logger = logging.getLogger(__name__)

BACKPRESSURE_WARNING_THRESHOLD: int = 100


class ServerFramerateCalculator:
    """Compute true camera capture framerate from (frame_number, capture_timestamp_ns) pairs."""

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
        self._observations.clear()
        self._per_frame_durations_ms.clear()


class WebsocketRelayHandler:
    def __init__(
        self,
        cgm: CameraGroupManager,
        send_bytes: Callable[[bytes], Awaitable[None]],
        send_json: Callable[[dict], Awaitable[None]],
        send_text: Callable[[str], Awaitable[None]],
        should_continue_fn: Callable[[], bool],
        signal_shutdown_fn: Callable[[], None],
        global_kill_flag,
    ):
        self._cgm = cgm
        self._send_bytes = send_bytes
        self._send_json = send_json
        self._send_text = send_text
        self._should_continue = should_continue_fn
        self._signal_shutdown = signal_shutdown_fn
        self._global_kill_flag = global_kill_flag

        self.last_sent_frame_number: int = -1
        self.last_received_frontend_confirmation: int = -1
        self._display_image_sizes: dict[CameraGroupIdString, dict[str, float]] | None = None
        self._server_framerate_calculators: dict[CameraGroupIdString, ServerFramerateCalculator] = {}
        self._display_framerate_trackers: dict[CameraGroupIdString, FramerateTracker] = {}
        self._last_framerate_send_time: float = 0.0

    def update_ack(self, frame_number: int, display_image_sizes) -> None:
        self.last_received_frontend_confirmation = frame_number
        self._display_image_sizes = display_image_sizes

    def check_frame_acknowledgment_status(self) -> bool:
        if self.last_sent_frame_number == -1:
            return True
        return self.last_received_frontend_confirmation >= self.last_sent_frame_number

    async def frontend_image_relay(self):
        """Relay image payloads from shared memory to the frontend via WebSocket."""
        logger.info("Starting frontend image payload relay...")
        try:
            skipped_previous = False
            while self._should_continue():
                await await_10ms()

                if not self._cgm.any_group_streaming():
                    continue

                if self.check_frame_acknowledgment_status():
                    if skipped_previous:
                        skipped_previous = False
                    else:
                        new_frontend_payloads = self._cgm.get_latest_frontend_payloads(
                            if_newer_than=self.last_sent_frame_number,
                            display_image_sizes=self._display_image_sizes,
                        )
                        for camera_group_id, (frame_number, multiframe_timestamp, payload_bytes) in new_frontend_payloads.items():
                            await self._send_bytes(payload_bytes)
                            self.last_sent_frame_number = frame_number

                            if camera_group_id not in self._server_framerate_calculators:
                                self._server_framerate_calculators[camera_group_id] = ServerFramerateCalculator(source_name="Server")
                            self._server_framerate_calculators[camera_group_id].update(
                                frame_number=frame_number,
                                capture_timestamp_ns=multiframe_timestamp,
                            )

                            if camera_group_id not in self._display_framerate_trackers:
                                self._display_framerate_trackers[camera_group_id] = FramerateTracker.create(framerate_source="Display")
                            self._display_framerate_trackers[camera_group_id].update(time.perf_counter_ns())
                else:
                    skipped_previous = True
                    backpressure = self.last_sent_frame_number - self.last_received_frontend_confirmation
                    if backpressure > BACKPRESSURE_WARNING_THRESHOLD and backpressure % BACKPRESSURE_WARNING_THRESHOLD == 0:
                        logger.trace(
                            f"Backpressure detected: {backpressure} frames not acknowledged by frontend! "
                            f"Last sent: {self.last_sent_frame_number}, last ack: {self.last_received_frontend_confirmation}"
                        )

                now = time.monotonic()
                if now - self._last_framerate_send_time >= 0.25:
                    for camera_group_id, server_calc in self._server_framerate_calculators.items():
                        if camera_group_id not in self._display_framerate_trackers:
                            continue
                        server_framerate = server_calc.current_framerate
                        display_tracker = self._display_framerate_trackers[camera_group_id]
                        if server_framerate and display_tracker.has_data:
                            msg = WebsocketFramerateUpdate(
                                camera_group_id=camera_group_id,
                                backend_framerate=server_framerate.model_dump(),
                                frontend_framerate=display_tracker.current_framerate.model_dump(),
                            )
                            await self._send_json(msg.model_dump())
                            server_calc.clear()
                            display_tracker.clear()
                    self._last_framerate_send_time = now

        except (WebSocketDisconnect, AssertionError):
            logger.info("Client disconnected, ending frontend image relay task...")
        except RuntimeError as e:
            if "close" in str(e).lower():
                logger.info("WebSocket closed during image relay send, ending task...")
            else:
                raise
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            self._global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()

    async def logs_relay(self, ws_log_level: int = LogLevels.TRACE.value):
        logger.info("Starting WebSocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self._should_continue():
                if not logs_queue.empty():
                    log_record: LogRecordModel = LogRecordModel(**logs_queue.get_nowait())
                    if log_record.levelno < ws_log_level:
                        continue
                    await self._send_json(log_record.model_dump())
                else:
                    await await_10ms()
        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")
        except (WebSocketDisconnect, AssertionError):
            logger.info("Client disconnected, ending log relay task...")
        except RuntimeError as e:
            if "close" in str(e).lower():
                logger.info("WebSocket closed during log relay send, ending task...")
            else:
                raise
        except Exception as e:
            logger.exception(f"Error in WebSocket log relay: {e.__class__}: {e}")
            self._global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()

    async def app_state_sender(self):
        """Periodically send the application state to the frontend."""
        logger.info("Starting state sender task...")
        previous_state: dict | None = None
        try:
            while self._should_continue():
                state_dict = self._cgm.to_state_dict()
                if previous_state is None or state_dict != previous_state:
                    msg = WebsocketAppState(state=state_dict)
                    await self._send_json(msg.model_dump())
                await asyncio.sleep(1.0)
                previous_state = state_dict
        except asyncio.CancelledError:
            logger.debug("State sender task cancelled")
        except (WebSocketDisconnect, AssertionError):
            logger.info("Client disconnected, ending state sender task...")
        except RuntimeError as e:
            if "close" in str(e).lower():
                logger.info("WebSocket closed during state send, ending task...")
            else:
                raise
        except Exception as e:
            logger.exception(f"Error in state sender: {e.__class__}: {e}")
            self._global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()
            logger.info("Ending state sender task...")
