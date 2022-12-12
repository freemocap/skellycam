import logging
from typing import Dict, Union

import cv2
import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout

from fast_camera_capture.qt_multi_camera_viewer.qt_camera_viewer import CameraViewWorker

logger = logging.getLogger(__name__)


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

        for camera_id in self._camera_ids:
            self._camera_worker_dictionary[camera_id] = {}
            self._camera_worker_dictionary[camera_id] = CameraViewWorker(
                camera_id=camera_id
            )

        self.add_widgets_to_layout()

    def add_widgets_to_layout(self):
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

    def update_images(self, image_dictionary: Dict[Union[int, str], np.ndarray]):

        for camera_id, image in image_dictionary.items():
            try:
                self._camera_worker_dictionary[camera_id].update_image(
                    image_dictionary[camera_id]
                )
            except Exception as e:
                logger.error(f"Error updating camera {camera_id} display: {e}")
