import logging
import time

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.viewers.qt_app.workers.cam.camworker import CamGroupFrameWorker

logger = logging.getLogger(__name__)


class QtMultiCameraViewerWidget(QWidget):
    def __init__(self, camera_ids: list, parent=None):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        if camera_ids is None:
            self._camera_ids = detect_cameras().cameras_found_list
        else:
            self._camera_ids = camera_ids

        self._camera_view_dict = {}

        self._camera_group_worker = CamGroupFrameWorker(self._camera_ids)
        self._camera_group_worker.start()

        self._multi_camera_grid_layout = self._camera_group_worker.camera_view_grid_layout
        self._layout.addLayout(self._multi_camera_grid_layout)

    @property
    def number_of_cameras(self):
        return len(self._camera_ids)


    def closeEvent(self, event):
        logger.info("Close Event detected - Closing QtMultiCameraViewerWidget")
        self._camera_group_worker.close()
