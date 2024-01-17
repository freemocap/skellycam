from PySide6.QtCore import Signal, QObject, QThread, QTimer
from pydantic import BaseModel

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import FrontendWebsocketConnection


class FrameRequester(QThread):
    new_frames = Signal(MultiFramePayload)

    def __init__(
        self,
        camera_websocket: FrontendWebsocketConnection,
        parent: QObject,
        frontend_framerate: float = 30,
    ):
        super().__init__(parent=parent)
        self.camera_websocket = camera_websocket
        self.camera_websocket.frames_received.connect(self.new_frames)
        self.should_continue = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._request_frames)
        self.frontend_framerate = frontend_framerate

    def start(self):
        logger.info(f"FrameGrabber starting...")
        self.camera_websocket.connect_websocket()

        # Fetch the framerate from the config and calculate interval.
        framerate = self.config.get(
            "framerate", 30
        )  # Define a default framerate if not set
        interval_ms = 1000 // framerate
        self.timer.start(interval_ms)

    def stop(self):
        logger.info("FrameGrabber stopping...")
        self.timer.stop()
        self.camera_websocket.disconnect_websocket()

    def _request_frames(self):
        logger.trace("Requesting new frames...")
        get_frames_request = GetFramesRequest()
        self.camera_websocket.send_outgoing_message(get_frames_request.dict())
