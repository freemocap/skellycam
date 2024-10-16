import json
import logging
import multiprocessing
import time
from typing import Union, Dict, Any

import websocket
from PySide6.QtWidgets import QWidget

from skellycam.app.app_state import AppStateDTO
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.videos.video_recorder_manager import RecordingInfo

logger = logging.getLogger(__name__)

from PySide6.QtCore import QThread, Signal

class WebsocketThread(QThread):
    message_received = Signal(str)
    error_occurred = Signal(str)
    connection_opened = Signal()
    connection_closed = Signal()

    def __init__(self, websocket_url: str, parent=None):
        super().__init__(parent)
        self.websocket_url = websocket_url
        self.websocket = self._create_websocket()

    def _create_websocket(self):
        return websocket.WebSocketApp(
            self.websocket_url,
            on_message=self._on_message,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    def run(self):
        self.websocket.run_forever(reconnect=True, ping_interval=5)

    def _on_open(self, ws):
        self.connection_opened.emit()

    def _on_message(self, ws, message):
        self.message_received.emit(message)

    def _on_error(self, ws, exception):
        self.error_occurred.emit(str(exception))

    def _on_close(self, ws, close_status_code, close_msg):
        self.connection_closed.emit()

class WebSocketClient(QWidget):
    new_frontend_payload_available = Signal(object)
    new_recording_info_available = Signal(object)
    new_app_state_available = Signal(object)

    def __init__(self,
                 base_url: str,
                 parent=None):
        super().__init__(parent)
        self.websocket_url = base_url.replace("http", "ws") + "/websocket/connect"
        self.websocket_thread = WebsocketThread(self.websocket_url)

        # Connect signals
        self.websocket_thread.message_received.connect(self._handle_websocket_message)
        self.websocket_thread.error_occurred.connect(self._handle_error)
        self.websocket_thread.connection_opened.connect(self._on_open)
        self.websocket_thread.connection_closed.connect(self._on_close)


    def connect_websocket(self):
        self.websocket_thread.start()

    def _handle_error(self, error_message: str):
        logger.exception(f"WebSocket exception: {error_message}")

    def _on_open(self):
        logger.info(f"Connected to WebSocket at {self.websocket_url}")

    def _on_close(self):
        logger.info(f"WebSocket connection closed, shutting down...")

    def _handle_websocket_message(self, message: Union[str, bytes]):
        if isinstance(message, str):
            try:
                json_data = json.loads(message)
                self._handle_json_message(json_data)
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON text message: {message}")
        elif isinstance(message, bytes):
            logger.info(f"Received binary message: size: {len(message) * .001:.3f}kB")
            self._handle_binary_message(message)

    def _handle_binary_message(self, message: bytes):
        try:
            payload = json.loads(message)
            self._process_payload(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding binary message: {e}")

    def _handle_json_message(self, message: Dict[str, Any]):
        try:
            self._process_payload(message)
        except Exception as e:
            logger.exception(f"Error processing JSON message: {e}")

    def _process_payload(self, payload: Dict[str, Any]):
        if 'jpeg_images' in payload:
            fe_payload = FrontendFramePayload(**payload)
            logger.info(f"Received FrontendFramePayload with {len(fe_payload.camera_ids)} cameras")
            fe_payload.lifespan_timestamps_ns.append({"received_from_websocket": time.perf_counter_ns()})
            self.new_frontend_payload_available.emit(fe_payload)
        elif 'recording_name' in payload:
            logger.info(f"Received RecordingInfo object: {payload}")
            self.new_recording_info_available.emit(RecordingInfo(**payload))
        elif 'camera_configs' in payload:
            app_state = AppStateDTO(**payload)
            logger.info(f"Received AppStateDTO with timestamp: {app_state.state_timestamp}")
            self.new_app_state_available.update_app_state(app_state_dto=app_state)
        else:
            logger.warning(f"Received unrecognized payload")

    def close(self):
        logger.info("Closing WebSocket client")
        if self.websocket_thread.isRunning():
            self.websocket_thread.quit()  # Gracefully stop the thread
            self.websocket_thread.wait()