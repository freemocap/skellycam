import multiprocessing

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from skellycam import logger
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload


class FrameGrabber(QThread):
    new_frames = Signal(MultiFramePayload)

    def __init__(self,
                 frontend_frame_pipe_receiver,  # multiprocessing.connection.Connection
                 stop_event: multiprocessing.Event,
                 parent=QWidget):
        super().__init__(parent=parent)
        self.stop_event = stop_event
        self.frontend_frame_pipe_receiver = frontend_frame_pipe_receiver

    def run(self):

        while True and not self.stop_event.is_set():
            try:
                payload_bytes = self.frontend_frame_pipe_receiver.recv_bytes()
                multi_frame_payload = MultiFramePayload.from_bytes(payload_bytes)
                # logger.trace(f"Got new multi-frame payload from backend! Emitting `new_frames` signal")
                self.new_frames.emit(multi_frame_payload)
            except Exception as e:
                logger.error(str(e))
                logger.exception(e)
                raise e
