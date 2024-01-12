from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget
from starlette.websockets import WebSocket

from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.backend.system.environment.get_logger import logger


class FrameGrabber(QThread):
    new_frames = Signal(MultiFramePayload)

    def __init__(
        self,
        multiframe_websocket: WebSocket,
        parent=QWidget,
    ):
        super().__init__(parent=parent)
        self.multiframe_websocket = multiframe_websocket
        self.daemon = True

    async def run(self):
        logger.info(f"FrameGrabber starting...")
        while True:
            try:
                multi_frame_payload_bytes = (
                    await self.multiframe_websocket.receive_bytes()
                )

                self.new_frames.emit(
                    MultiFramePayload.from_bytes(multi_frame_payload_bytes)
                )
            except Exception as e:
                logger.error(str(e))
                logger.exception(e)
