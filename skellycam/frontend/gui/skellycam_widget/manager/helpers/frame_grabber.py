from PySide6.QtCore import Signal, QObject

from skellycam.api.frontend_client.api_client import FrontendApiClient
from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger


class FrameGrabber(QObject):
    new_frames = Signal(MultiFramePayload)

    def __init__(self, api_client: FrontendApiClient, parent: QObject):
        super().__init__(parent=parent)
        self.api_client = api_client
        self.should_continue = True

    async def start_loop(self):
        logger.info(f"FrameGrabber starting...")
        websocket = await self.api_client.get_websocket()

        while self.should_continue:
            try:
                multi_frame_payload_bytes = await websocket.recv()

                self.new_frames(MultiFramePayload.from_bytes(multi_frame_payload_bytes))
            except Exception as e:
                logger.error(str(e))
                logger.exception(e)
