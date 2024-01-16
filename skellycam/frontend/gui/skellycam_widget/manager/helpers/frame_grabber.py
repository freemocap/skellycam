import time

from PySide6.QtCore import Signal, QObject, QThread

from skellycam.api.frontend_client.api_client import FrontendApiClient
from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger


class FrameGrabber(QThread):
    new_frames = Signal(MultiFramePayload)

    def __init__(self, api_client: FrontendApiClient, parent: QObject):
        super().__init__(parent=parent)
        self.api_client = api_client
        self.should_continue = True

    def run(self):
        logger.info(f"FrameGrabber starting...")

        while self.should_continue:
            time.sleep(0.001)
            try:
                logger.trace(f"Grabbing new frames...")
                multi_frame_payload = self.api_client.get_latest_frames()
                if multi_frame_payload:
                    self.new_frames.emit(multi_frame_payload)
            except Exception as e:
                logger.error(str(e))
                logger.exception(e)
