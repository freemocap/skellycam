from PyQt6.QtCore import pyqtSignal, QThread
from skellycam.backend.controller.core_functionality.detection import detect_cameras

from skellycam import logger


class DetectCamerasWorker(QThread):
    cameras_detected_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        logger.info("Starting detect cameras thread worker")
        camera_ids = detect_cameras(use_cache=False).cameras_found_list
        self.cameras_detected_signal.emit(camera_ids)
