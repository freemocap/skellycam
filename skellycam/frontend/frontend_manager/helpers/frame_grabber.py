import multiprocessing
from typing import Dict

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget


class FrameGrabber(QThread):
    new_images = Signal(dict)

    def __init__(self, incoming_frame_queue: multiprocessing.Queue, parent=QWidget):
        super().__init__(parent=parent)
        self.incoming_frame_queue = incoming_frame_queue

    def run(self):
        while True:
            try:
                q_images: Dict[str, QImage] = self.incoming_frame_queue.get(block=True)

                self.new_images.emit(q_images)
            except Exception as e:
                print(f"Error in FrameGrabber: {e}")
                break
