import json
import logging
import threading
import time
from typing import Union, Dict, Any, Optional, Callable

import msgpack
import websocket
from websocket import WebSocketApp

from skellycam.api.app.app_state import AppStateDTO
from skellycam.api.routes.websocket.websocket_server import HELLO_CLIENT_BYTES_MESSAGE, CLOSE_WEBSOCKET_MESSAGE
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.videos.video_recorder_manager import RecordingInfo
from skellycam.gui.gui_state import GUIState, get_gui_state

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    A simple WebSocket client that connects to a WebSocket server and handles incoming messages.
    Intended to be used as part of the FastAPIClient class.
    """

    def __init__(self, base_url: str):
        self.websocket_url = base_url.replace("http", "ws") + "/websocket/connect"
        self.websocket = self._create_websocket()
        self._websocket_thread: Optional[threading.Thread] = None
        self._gui_state: GUIState = get_gui_state()
        self._image_update_callable: Optional[Callable] = None

    def _create_websocket(self):
        return websocket.WebSocketApp(
            self.websocket_url,
            on_message=self._on_message,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    @property
    def connected(self) -> bool:
        return self.websocket.sock and self.websocket.sock.connected

    def connect_websocket(self) -> None:
        logger.info(f"Connecting to WebSocket at {self.websocket_url}...")
        self._websocket_thread = threading.Thread(
            target=lambda: self.websocket.run_forever(reconnect=True, ping_interval=5),
            daemon=True)
        self._websocket_thread.start()

    def _on_open(self, ws) -> None:
        logger.info(f"Connected to WebSocket at {self.websocket_url}")

    def _on_message(self, ws: WebSocketApp, message: Union[str, bytes]) -> None:
        self._handle_websocket_message(message)

    def _on_error(self, ws: WebSocketApp, exception: Exception) -> None:
        logger.exception(f"WebSocket exception: {exception.__class__.__name__}: {exception}")
        raise exception

    def _on_close(self, ws: WebSocketApp, close_status_code, close_msg) -> None:
        logger.info(f"WebSocket connection closed: Close status code: {close_status_code}, Close message: {close_msg}")

    def _handle_websocket_message(self, message: Union[str, bytes]) -> None:
        if isinstance(message, str):
            try:
                json_data = json.loads(message)
                self._handle_json_message(json_data)
            except json.JSONDecodeError:
                logger.info(f"Received text message: {message}")
                self._handle_text_message(message)
        elif isinstance(message, bytes):
            logger.loop(f"Received binary message: size: {len(message) * .001:.3f}kB")
            self._handle_binary_message(message)

    def _handle_text_message(self, message: str) -> None:
        logger.info(f"Received text message: {message}")
        pass

    def _handle_binary_message(self, message: bytes) -> None:
        if message == HELLO_CLIENT_BYTES_MESSAGE:
            logger.info("Received HELLO_CLIENT_BYTES_MESSAGE")
            return
        payload = msgpack.loads(message)
        if isinstance(payload, FrontendFramePayload):
            logger.loop(
                f"Received FrontendFramePayload with {len(payload.camera_ids)} cameras - size: {len(message)} bytes")
            payload.lifespan_timestamps_ns.append({"unpickled_from_websocket": time.perf_counter_ns()})
            self._gui_state.latest_frontend_payload = payload
        elif isinstance(payload, RecordingInfo):
            logger.info(f"Received RecordingInfo for recording: `{payload.recording_name}`")
            self._gui_state.recording_info = payload
        elif isinstance(payload, AppStateDTO):
            logger.info(f"Received AppStateDTO (state_timestamp: {payload.state_timestamp})")
            self._gui_state.update_app_state(app_state_dto=payload)
        else:
            logger.info(f"Received binary message: {len(payload) * .001:.3f}kB")

    def _handle_json_message(self, message: Dict[str, Any]) -> None:
        if "message" in message:
            logger.info(f"Received message: {message['message']}")
        else:
            logger.info(f"Received JSON message, size: {len(json.dumps(message))} bytes")

    def send_message(self, message: Union[str, bytes, Dict[str, Any]]) -> None:
        if self.websocket:
            if isinstance(message, dict):
                self.websocket.send(json.dumps(message))
                logger.info(f"Sent JSON message: {message}")
            elif isinstance(message, str):
                self.websocket.send(message)
                logger.info(f"Sent text message: {message}")
            elif isinstance(message, bytes):
                self.websocket.send(message)
                logger.info(f"Sent binary message of length {len(message)}")

    def close(self) -> None:

        if self.websocket:
            try:
                self.websocket.send(CLOSE_WEBSOCKET_MESSAGE)
                self.websocket.close()
            except websocket.WebSocketConnectionClosedException:
                pass
        self.websocket = self._create_websocket()
        logger.info("Closing WebSocket client")
        if self._websocket_thread:
            self._websocket_thread.join()
