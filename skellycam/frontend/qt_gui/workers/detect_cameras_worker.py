import logging

from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtMultimedia import QMediaDevices

from skellycam.backend.opencv.detection.detect_cameras import detect_cameras

logger = logging.getLogger(__name__)


class DetectCamerasWorker(QThread):
    cameras_detected_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._devices = QMediaDevices()

    def run(self):
        logger.info("Starting detect cameras thread worker")
        available_cameras = self._devices.videoInputs()
        camera_info = {}
        for camera_number, camera in available_cameras:
            position = camera.position()
            camera_info[camera_id] = self._devices.deviceDescription(camera_id)
        self.cameras_detected_signal.emit(camera_ids)

if __name__ == "__main__":
    f = QMediaDevices()
    f=9