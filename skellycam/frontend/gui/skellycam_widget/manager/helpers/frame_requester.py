from PySide6.QtCore import Signal, QObject, QTimer

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import (
    FrontendWebsocketManager,
    GetFramesWebsocketRequest,
)


class FrameRequester(QObject):
    new_frames = Signal(MultiFramePayload)

    def __init__(
        self,
        websocket_connection: FrontendWebsocketManager,
        parent: QObject,
        frontend_framerate: float = 30,
    ):
        super().__init__(parent=parent)
        self.websocket_connection = websocket_connection
        self.websocket_connection.frames_received.connect(self.new_frames)
        self.should_continue = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._request_frames)
        self.frontend_framerate = frontend_framerate

    def start(self):
        logger.info(f"FrameRequester starting...")
        self.websocket_connection.connect_websocket()

        interval_ms = 1000 // self.frontend_framerate
        self.timer.start(int(interval_ms))

    def stop(self):
        logger.info("FrameGrabber stopping...")
        self.timer.stop()
        self.websocket_connection.disconnect_websocket()

    def _request_frames(self):
        logger.debug("Requesting new frames...")
        self.websocket_connection.send_ping()
        # self.websocket_connection.request_frames()
