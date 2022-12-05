from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QMainWindow

from fast_camera_capture.opencv.viewer.qt_app.workers.cam.camworker import (
    CamFrameWorker,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker = CamFrameWorker(["0"])
        self._worker.start()
        self._worker.ImageUpdate.connect(self._handle_image_update)
        self._video_label = QLabel()

        self.setCentralWidget(self._video_label)

    def _handle_image_update(self, cam_id, image):
        self._video_label.setPixmap(QPixmap.fromImage(image))
