from PySide6.QtCore import QObject, QTimer, QThread

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketManager


class FrameRequester(QObject):
    def __init__(
        self,
        websocket_connection: FrontendWebsocketManager,
        parent: QObject,
        frontend_framerate: float = 30,
    ):
        super().__init__(parent=parent)
        self.websocket_connection = websocket_connection
        self.should_continue = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._request_frames)
        self.frontend_framerate = frontend_framerate

    def start(self):
        logger.info(f"FrameRequester starting...")

        interval_ms = 1000 // self.frontend_framerate
        self.timer.start(int(interval_ms))

    def stop(self):
        logger.info("FrameGrabber stopping...")
        self.timer.stop()

    def _request_frames(self):
        logger.trace("Requesting new frames...")
        self.websocket_connection.request_frames()  # sends a message to the server to request frames, which will be caught by the websocket handler and emitted as a signal
