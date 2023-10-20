import multiprocessing

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from skellycam import logger
from skellycam.models.cameras.frames.multiframe_payload import MultiFramePayload


class FrameGrabber(QThread):
    new_frames = Signal(MultiFramePayload)

    def __init__(self,
                 incoming_frame_queue: multiprocessing.Queue,
                 stop_event: multiprocessing.Event,
                 parent=QWidget):
        super().__init__(parent=parent)
        self.stop_event = stop_event
        self.incoming_frame_queue = incoming_frame_queue

    def run(self):

        while True and not self.stop_event.is_set():
            try:
                payload: MultiFramePayload = self.incoming_frame_queue.get(block=True)
                # logger.trace(f"Got new multi-frame payload from backend! Emitting `new_frames` signal")
                self.new_frames.emit(payload)
            except Exception as e:
                logger.error(str(e))
                logger.exception(e)
                raise e
