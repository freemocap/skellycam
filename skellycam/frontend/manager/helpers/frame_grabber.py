from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from skellycam.system.environment.get_logger import logger
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload


class FrameGrabber(QThread):
    new_frames = Signal(MultiFramePayload)

    def __init__(self,
                 frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection
                 parent=QWidget):
        super().__init__(parent=parent)
        self.frontend_frame_pipe_receiver = frontend_frame_pipe_receiver
        self.daemon = True

    def run(self):
        logger.info(f"FrameGrabber starting...")
        while True:
            try:
                multi_frame_payload_bytes = self.frontend_frame_pipe_receiver.recv_bytes()  # waits here until there is something to receive
                multi_frame_payload = MultiFramePayload.from_bytes(multi_frame_payload_bytes)
                self.new_frames.emit(multi_frame_payload)
            except Exception as e:
                logger.error(str(e))
                logger.exception(e)
                raise e
