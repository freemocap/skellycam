import json
import logging
import threading
import time
from typing import Union, Dict, Any, Optional

import websocket

from skellycam.api.routes.websocket.websocket_server import FRONTEND_READY_FOR_NEXT_PAYLOAD_TEXT
from skellycam.core.frames.frame_saver import RecordingInfo
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload
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

    def _create_websocket(self):
        return websocket.WebSocketApp(
            self.websocket_url,
            on_message=self._on_message,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    def connect(self) -> None:
        logger.info(f"Connecting to WebSocket at {self.websocket_url}...")
        self._websocket_thread = threading.Thread(target=lambda: self.websocket.run_forever(reconnect=True),
                                                  daemon=True)
        self._websocket_thread.start()

    def _on_open(self, ws) -> None:
        logger.info(f"Connected to WebSocket at {self.websocket_url}")

    def _on_message(self, ws, message: Union[str, bytes]) -> None:
        self._handle_websocket_message(message)

    def _on_error(self, ws, error) -> None:
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        logger.info("WebSocket connection closed")

    def _handle_websocket_message(self, message: Union[str, bytes]) -> None:
        if isinstance(message, str):
            try:
                json_data = json.loads(message)
                self._handle_json_message(json_data)
            except json.JSONDecodeError:
                logger.info(f"Received text message: {message}")
                self._handle_text_message(message)
        elif isinstance(message, bytes):
            logger.info(f"Received binary message of length {len(message)}")
            self._handle_binary_message(message)

    def _handle_text_message(self, message: str) -> None:
        logger.info(f"Received text message: {message}")
        pass

    def _handle_binary_message(self, message: bytes) -> None:
        logger.info(f"Received binary message of length {len(message)}")
        pass

    def _handle_json_message(self, message: Dict[str, Any]) -> None:
        if "jpeg_images" in message:
            fe_payload = FrontendFramePayload(**message)
            logger.loop(f"Received FrontendFramePayload with {len(fe_payload.camera_ids)} cameras")
            fe_payload.lifespan_timestamps_ns.append({"received_from_websocket": time.perf_counter_ns()})
            self._gui_state.latest_frontend_payload = fe_payload
            self.websocket.send_text(FRONTEND_READY_FOR_NEXT_PAYLOAD_TEXT)
        elif "recording_name" in message:
            recording_info = RecordingInfo(**message)
            logger.info(f"Received RecordingInfo: {recording_info}")
            self._gui_state.recording_info = recording_info
        else:
            logger.info(f"Received JSON message: {message}")

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
            self.websocket.close()
        self.websocket = self._create_websocket()
        logger.info("Closing WebSocket client")
        if self._websocket_thread:
            self._websocket_thread.join()
