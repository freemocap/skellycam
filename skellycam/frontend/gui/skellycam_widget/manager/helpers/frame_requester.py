from PySide6.QtCore import QObject, QTimer, QThread

from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketClient


class FrameRequester(QObject):
    def __init__(
        self,
        websocket_client: FrontendWebsocketClient,
        parent: QObject,
    ):
        super().__init__(parent=parent)
        self.websocket_connection = websocket_client
        self.should_continue = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._request_frames)

    def start(self, target_frames_per_second: float):
        logger.info(f"FrameRequester starting...")

        interval_ms = 1000 // target_frames_per_second
        self.timer.start(int(interval_ms))

    def stop(self):
        logger.info("FrameGrabber stopping...")
        self.timer.stop()

    def _request_frames(self):
        logger.trace("Requesting new frames...")
        self.websocket_connection.request_frames()  # sends a message to the server to request frames, which will be caught by the websocket handler and emitted as a signal
