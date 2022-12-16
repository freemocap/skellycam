import logging
from typing import Union, List

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget, QGridLayout, QVBoxLayout, QPushButton


from fast_camera_capture.qt_gui.workers.camera_group_frame_worker import (
    CamGroupFrameWorker,
)
from fast_camera_capture.qt_gui.workers.detect_cameras_worker import DetectCamerasWorker

logger = logging.getLogger(__name__)


class QtMultiCameraViewerWidget(QWidget):
    cameras_connected_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    incoming_camera_configs_signal = pyqtSignal(dict)

    def __init__(self, camera_ids: List[Union[str, int]] = None, parent=None):

        self._camera_config_dicationary = None
        self._detect_cameras_worker = None
        self._video_label_dict = None
        logger.info(
            f"Initializing QtMultiCameraViewerWidget with camera_ids: {camera_ids}"
        )
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_ids = camera_ids
        self._cam_group_frame_worker = self._create_cam_group_frame_worker()
        if self._camera_ids is None:
            self._detect_available_cameras_push_button = (
                self._create_detect_cameras_button()
            )
            self._layout.addWidget(self._detect_available_cameras_push_button)
        else:
            self.connect_to_cameras()

    @property
    def controller_slot_dictionary(self):
        return self._cam_group_frame_worker.slot_dictionary

    @property
    def camera_config_dicationary(self):
        return self._camera_config_dicationary

    def _handle_image_update(self, camera_id, image):
        self._video_label_dict[camera_id]["image_label"].setPixmap(
            QPixmap.fromImage(image)
        )

    def _create_camera_view_grid_layout(
        self, camera_ids: List[Union[str, int]]
    ) -> dict:
        self._camera_view_grid_layout = QGridLayout()
        self._layout.addLayout(self._camera_view_grid_layout)

        number_of_columns = np.ceil(np.sqrt(len(camera_ids)))
        video_label_dict = {}
        column_count = 0
        row_count = 0

        for camera_id in camera_ids:

            video_label_dict[camera_id] = {}
            video_label_dict[camera_id]["title_label"] = QLabel(f"Camera {camera_id} ")
            video_label_dict[camera_id]["image_label"] = QLabel(f"connecting... ")
            camera_layout = QVBoxLayout()
            camera_layout.addWidget(video_label_dict[camera_id]["title_label"])
            camera_layout.addWidget(video_label_dict[camera_id]["image_label"])

            self._camera_view_grid_layout.addLayout(
                camera_layout, row_count, column_count
            )

            # This section is for formatting the videos in the grid nicely - it fills out two columns and then moves on to the next row
            column_count += 1
            if column_count % number_of_columns == 0:
                column_count = 0
                row_count += 1

        return video_label_dict

    def connect_to_cameras(self):
        logger.info("Connecting to cameras")

        if self._camera_ids is None:
            logger.info("No camera ids provided - detecting available cameras")
            self._detect_available_cameras_push_button.setText("Detecting Cameras...")
            self._detect_available_cameras_push_button.setEnabled(False)

            self._detect_cameras_worker = DetectCamerasWorker()
            self._detect_cameras_worker.cameras_detected_signal.connect(
                self._handle_detected_cameras
            )
            self._detect_cameras_worker.start()

        else:
            self._start_camera_group_frame_worker(self._camera_ids)

    def _handle_detected_cameras(self, camera_ids):
        logger.info(f"Detected cameras: {camera_ids}")
        self._camera_ids = camera_ids
        self._start_camera_group_frame_worker(self._camera_ids)

    def _start_camera_group_frame_worker(self, camera_ids):
        logger.info(f"Starting camera group frame worker with camera_ids: {camera_ids}")
        self._video_label_dict = self._create_camera_view_grid_layout(
            camera_ids=camera_ids
        )
        self._cam_group_frame_worker.camera_ids = camera_ids
        self._cam_group_frame_worker.start()
        self._cam_group_frame_worker.ImageUpdate.connect(self._handle_image_update)

    def disconnect_from_cameras(self):
        self._cam_group_frame_worker.close()

    def pause(self):
        self._cam_group_frame_worker.pause()

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self._cam_group_frame_worker.close()
        self.close()

    def _create_detect_cameras_button(self):
        detect_available_cameras_push_button = QPushButton("Detect Available Cameras")
        detect_available_cameras_push_button.clicked.connect(self.connect_to_cameras)
        detect_available_cameras_push_button.hasFocus()
        return detect_available_cameras_push_button

    def _create_cam_group_frame_worker(self):
        cam_group_frame_worker = CamGroupFrameWorker(self._camera_ids)

        cam_group_frame_worker.cameras_connected_signal.connect(
            self.cameras_connected_signal.emit
        )
        cam_group_frame_worker.camera_group_created_signal.connect(
            self.camera_group_created_signal.emit
        )

        self.incoming_camera_configs_signal.connect(
            cam_group_frame_worker.update_camera_group_configs
        )
        return cam_group_frame_worker


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    qt_multi_camera_viewer_widget = QtMultiCameraViewerWidget()
    main_window.setCentralWidget(qt_multi_camera_viewer_widget)
    main_window.show()
    error_code = app.exec()
    qt_multi_camera_viewer_widget.close()

    sys.exit()
