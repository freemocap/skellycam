import json
from typing import Literal, Union

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtWebSockets import QWebSocket
from pydantic import BaseModel

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger


class WebsocketRequest(BaseModel):
    command: Literal["get_frames", "ping"]


class WebsocketResponse(BaseModel):
    success: bool
    data: Union[MultiFramePayload, Literal["pong"]]


class FrontendWebsocketConnection(QWebSocket):
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)
    message_received = Signal(dict)
    frames_received = Signal(MultiFramePayload)

    def __init__(self, url: str, parent: QObject = None):
        super().__init__(parent)
        self.url = url
        self.connected.connect(self.on_connected)
        self.disconnected.connect(self.on_disconnected)
        self.textMessageReceived.connect(self.on_text_message_received)
        self.error.connect(self.on_error)
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self.check_connection)
        self.reconnect_timer.start(1000)  # Time in milliseconds (e.g., 10000ms = 10s)

    def check_connection(self):
        if not self.isValid():
            logger.warning("WebSocket connection dropped. Attempting to reconnect...")
            self.connect_websocket()

    def open_connection(self, url: str):
        self.open(url)

    def on_connected(self):
        logger.info("WebSocket connected!")
        self.connected.emit()

    def on_disconnected(self):
        logger.info("WebSocket disconnected")
        self.disconnected.emit()

    def on_error(self, error_code):
        error_message = self.errorString()
        logger.error(f"WebSocket error ({error_code}): {error_message}")
        self.error_occurred.emit(error_message)

    def on_text_message_received(self, message: str):
        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except json.JSONDecodeError as e:
            logger.info(f"Error decoding message: {e}")
            self.error_occurred.emit(str(e))

    def send_outgoing_message(self, message: dict):
        message_str = json.dumps(message)
        self.sendTextMessage(message_str)

    def handle_incoming_message(self, message: str):
        try:
            # data = json.loads(message)
            multi_frame_payload = MultiFramePayload.from_bytes(message)
            self.frames_received.emit(multi_frame_payload)
        except Exception as e:
            logger.error(f"Failed to handle websocket message: {e}")

    def disconnect_websocket(self):
        logger.info("Disconnecting from websocket")
        self.close()

    def connect_websocket(self):
        logger.info(f"Connecting to websocket...")
        self.message_received.connect(self.handle_incoming_message)
        self.open_connection(self.url)
        logger.info("Successfully connected to websocket")

    def request_frames(self):
        # Create a request to fetch frames
        get_frames_request = WebsocketRequest()
        self.send_outgoing_message(get_frames_request.dict())
