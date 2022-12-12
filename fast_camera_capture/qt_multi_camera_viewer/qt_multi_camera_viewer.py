import logging
import time
from typing import Dict, Union

import numpy as np
from PyQt6.QtCore import QThread

from PyQt6.QtWidgets import QWidget, QGridLayout, QMainWindow, QApplication

from fast_camera_capture.detection.models.frame_payload import FramePayload
from fast_camera_capture.qt_multi_camera_viewer.qt_camera_viewer import CameraViewWorker

logger = logging.getLogger(__name__)

class QtMultiCameraViewerThread(QThread):
    def __init__(self, camera_ids:list):
        super().__init__()
        self._qt_app = QApplication([])
        self._qt_multi_camera_viewer = QtMultiCameraViewerWidget(camera_ids=camera_ids)

    def show(self):
        self._qt_multi_camera_viewer.show()

    def update_image(self, frame_payload: FramePayload):
        self._qt_multi_camera_viewer.update_image(frame_payload)

    def run(self):
        logger.info("Starting QtMultiCameraViewerThread")
        while True:
            self._qt_app.exec()
            time.sleep(0.001)

class QtMultiCameraViewerWidget(QWidget):
    def __init__(self, camera_ids: list):
        super().__init__()

        self._layout = QGridLayout()
        self.setLayout(self._layout)

        self._camera_worker_dictionary = {}

        self._camera_ids = camera_ids
        self.generate_camera_view_grid()

    @property
    def number_of_cameras(self):
        return len(self._camera_ids)

    def generate_camera_view_grid(self):
        logger.debug("Generating camera view grid")
        for camera_id in self._camera_ids:
            self._camera_worker_dictionary[camera_id] = {}
            self._camera_worker_dictionary[camera_id] = CameraViewWorker(
                camera_id=camera_id
            )

        self.add_widgets_to_layout()

    def add_widgets_to_layout(self):
        logger.debug("Adding widgets to layout")
        column_count = 0
        row_count = 0
        for camera_worker in self._camera_worker_dictionary.values():
            self._layout.addWidget(
                camera_worker.q_label_widget, row_count, column_count
            )

            # This section is for formatting the videos in the grid nicely - it fills out two columns and then moves on to the next row
            column_count += 1
            if column_count % 2 == 0:
                column_count = 0
                row_count += 1

    def update_image(self, frame_payload: FramePayload):

        try:
            self._camera_worker_dictionary[frame_payload.camera_id].update_image(
                frame_payload.image
            )
        except Exception as e:
            logger.error(f"Error updating camera {frame_payload.camera_id} display: {e}")
