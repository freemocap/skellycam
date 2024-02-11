import json

from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtWebSockets import QWebSocket
from pydantic import BaseModel
from pydantic import ValidationError
from typing_extensions import Literal

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger


class BaseWebsocketRequest(BaseModel):
    command: str


class FrontendWebsocketManager(QWebSocket):
    frames_received = Signal(MultiFramePayload)

    def __init__(self, url: str, parent: QObject = None):
        super().__init__(parent)
        self.url = url
        self.connected.connect(self._handle_connected)
        self.disconnected.connect(self._handle_disconnected)
        self.textMessageReceived.connect(self._handle_incoming_message)
        self.error.connect(self._handle_error)

        self.destroyed.connect(self.disconnect_websocket)

        # Check connection every second and reconnect if necessary
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self._check_connection)
        self.reconnect_timer.start(1000)  # Time in milliseconds (e.g., 10000ms = 10s)

    def connect_websocket(self):
        logger.info(f"Connecting to websocket...")
        self._open_connection()
        logger.info("Successfully connected to websocket")

    def disconnect_websocket(self):
        logger.info("Disconnecting from websocket")
        self.close()

    def request_frames(self):
        # Create a request to fetch frames
        self.sendTextMessage("give frames, plz")

    def _open_connection(self):
        logger.debug(f"Opening websocket connection to {self.url}")
        self.open(self.url)

    def _check_connection(self):
        logger.debug(f"Checking connection to {self.url}")
        if not self.isValid():
            logger.warning("WebSocket connection dropped. Attempting to reconnect...")
            self.connect_websocket()
        logger.debug(f"WebSocket connection is working!")

    def _handle_connected(self):
        logger.info("WebSocket connected!")

    def _handle_disconnected(self):
        logger.info("WebSocket disconnected")

    def _handle_error(self, error_code):
        error_message = self.errorString()
        logger.error(f"WebSocket error ({error_code}): {error_message}")

    def _handle_incoming_message(self, message: bytes):
        try:
            logger.debug(f"incoming message with length: {len(message)}")

            multi_frame_payload = MultiFramePayload.from_bytes(message)
            self.frames_received.emit(multi_frame_payload)
        except ValidationError as e:
            logger.error(f"Failed to parse response as MultiFramePayload: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to handle websocket message: {e}")
            raise e
