import json
import time

from PySide6.QtCore import Signal, QObject, QTimer, QUrl
from PySide6.QtWebSockets import QWebSocket
from pydantic import ValidationError

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger


class FrontendWebsocketClient:
    def __init__(self, url: str):
        self.websocket = QWebSocket()
        self.url = url
        self.websocket.connected.connect(self.on_connected)
        self.websocket.binaryMessageReceived.connect(self.on_binary_message_received)
        self.connect_to_server()

    def connect_to_server(self, max_attempts: int = 5, interval: int = 2):
        logger.info("Connecting to websocket server")
        self.websocket.open(self.url)
        attempts = 0
        while not self.websocket.isValid() and attempts < max_attempts:
            logger.error(f"Failed to connect to websocket server at {self.url}")
            time.sleep(interval)

    def on_connected(self):
        logger.info("WebSocket connected!")
        self.send_ping()

    def send_ping(self):
        logger.info("Sending ping to server")
        self.websocket.sendBinaryMessage(b"ping")

    def on_binary_message_received(self, message):
        print(f"Received binary message: {message}")


class FrontendWebsocketManager(QWebSocket):
    """
    A class to manage the connection to the FRONTEND websocket server.
    This connection has one purpose: to receive frames from the backend and emit them as a signal.
    Other communication happens through the REST API.
    """

    frames_received = Signal(MultiFramePayload)

    def __init__(self, url: str, parent: QObject = None):
        super().__init__(parent)
        self.url = url
        self.binaryMessageReceived.connect(self._handle_incoming_message)
        self.error.connect(self._handle_error)

        self.destroyed.connect(self.disconnect_websocket)

        self.pong.connect(self._handle_pong)

        # Check connection every second and reconnect if necessary
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self._check_connection)
        self.reconnect_timer.start(1000)  # Time in milliseconds (e.g., 10000ms = 10s)

    def connect_websocket(self):
        logger.info(f"Connecting to websocket...")
        self._open_connection()
        while not self.isValid():
            logger.warning(f"Failed to connect to websocket. Retrying...")
            time.sleep(1)
            self._open_connection()
        logger.info("Successfully connected to websocket")

    def disconnect_websocket(self):
        logger.info("Disconnecting from websocket")
        self.close()

    def request_frames(self):
        # Create a request to fetch frames
        self.sendBinaryMessage(b"give-frames-plz")

    def _handle_pong(self, elapsedTime: int, payload: bytes):
        logger.debug(
            f"Received PONG with payload: {payload} and round-trip time: {elapsedTime} ms"
        )

    def _open_connection(self):
        logger.debug(f"Opening websocket connection to {self.url}")
        self.open(self.url)
        self.pingTimer = QTimer(self)
        self.pingTimer.timeout.connect(lambda: self.ping(b"Ping!"))
        self.pingTimer.start(30000)  # Send ping every 30 seconds

    def _check_connection(self):
        logger.debug(f"Checking connection to {self.url}")
        if not self.isValid():
            logger.warning("WebSocket connection dropped. Attempting to reconnect...")
            self.connect_websocket()
        logger.debug(f"WebSocket connection is working!")

    def _handle_error(self, error_code):
        error_message = self.errorString()
        logger.error(f"WebSocket error ({error_code}): {error_message}")

    def _handle_incoming_message(self, message: bytes):
        if message == b"pong":
            logger.info("Received Pong!")
            return
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
