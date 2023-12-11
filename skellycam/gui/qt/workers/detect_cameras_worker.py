import logging

from PySide6.QtCore import Signal, QThread

from skellycam.detection.detect_cameras import detect_cameras

logger = logging.getLogger(__name__)


class DetectCamerasWorker(QThread):
    cameras_detected_signal = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        logger.info("Starting detect cameras thread worker")
        camera_ids = detect_cameras(use_cache=False).cameras_found_list
        self.cameras_detected_signal.emit(camera_ids)
