import json
import logging
import threading
from typing import Union, Dict, Any, Optional

import websocket

from skellycam.core.frames.payload_models.multi_frame_payload import MultiFramePayload

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    A simple WebSocket client that connects to a WebSocket server and handles incoming messages.
    Intended to be used as part of the FastAPIClient class.
    """

    def __init__(self, base_url: str):
        self.websocket_url = base_url.replace("http", "ws") + "/websocket/connect"
        self.websocket = self._create_websocket()
        self._latest_frames: Optional[MultiFramePayload] = None
        self._new_frames_ready = False
        self._websocket_thread: Optional[threading.Thread] = None

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

    @property
    def latest_frames(self):
        self._new_frames_ready = False
        return self._latest_frames

    @latest_frames.setter
    def latest_frames(self, value: MultiFramePayload):
        self._new_frames_ready = True
        self._latest_frames = value

    @property
    def new_frames_ready(self):
        return self._new_frames_ready

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
                logger.info(f"Received JSON message: {json_data}")
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
                self.websocket.send_binary(message)
                logger.info(f"Sent binary message of length {len(message)}")

    def close(self) -> None:
        if self.websocket:
            self.websocket.close()
        self.websocket = self._create_websocket()
        logger.info("Closing WebSocket client")
