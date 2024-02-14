import logging

from PySide6.QtCore import Signal, QUrl
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QWidget
from pydantic import ValidationError

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload

FRAMES_REQUEST_STRING = "Send-frames-plz"

logger = logging.getLogger(__name__)


class FrontendWebsocketClient(QWidget):
    new_frames_received = Signal(MultiFramePayload)

    def __init__(self, url: str):
        super().__init__()
        logger.debug(f"Creating websocket client at url: {url}")
        self.url = QUrl(url)
        self.websocket = QWebSocket()
        self.websocket.connected.connect(self.on_connected)
        self.websocket.binaryMessageReceived.connect(self.on_binary_message_received)
        self.websocket.textMessageReceived.connect(self.on_text_message_received)

        self.websocket.error.connect(self.on_error)

        self.connect_to_server()

    def connect_to_server(self):
        logger.info("Connecting to websocket server")
        self.websocket.open(self.url)

    def on_connected(self):
        logger.success("WebSocket connected!")
        self.send_ping()

    def on_error(self, error_code):
        error_message = self.websocket.errorString()
        logger.error(f"WebSocket error ({error_code}): {error_message}")

    def send_ping(self):
        logger.info("Sending ping to server")
        self.websocket.sendTextMessage("Ping!")

    def request_frames(self):
        logger.trace("Sending request for frames")
        # Create a request to fetch frames
        self.websocket.sendTextMessage(FRAMES_REQUEST_STRING)

    def on_binary_message_received(self, binary_message: bytes):
        logger.trace(f"Received binary message with length: {len(binary_message)}")
        try:
            multi_frame_payload = MultiFramePayload.from_bytes(binary_message)
            self.new_frames_received.emit(multi_frame_payload)
        except ValidationError as e:
            logger.error(f"Failed to parse response as MultiFramePayload: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to handle websocket message: {e}")
            raise e

    def on_text_message_received(self, text_message: str):
        logger.info(f"Received text message: {text_message}")
        if text_message == "Pong!":
            logger.info("Received Pong!")
            return
        raise ValueError(f"Received unexpected text message: {text_message}")
