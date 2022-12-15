import logging
from typing import Union, List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget, QGridLayout, QVBoxLayout, QPushButton

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.opencv.video_recorder.save_synchronized_videos import save_synchronized_videos
from fast_camera_capture.viewers.qt_app.workers.camera_group_frame_worker import (
    CamGroupFrameWorker,
)

logger = logging.getLogger(__name__)


class QtMultiCameraViewerWidget(QWidget):
    cameras_connected_signal = pyqtSignal()

    def __init__(self,
                 camera_ids: List[Union[str, int]] = None,
                 parent=None):

        self._video_label_dict = None
        logger.info(f"Initializing QtMultiCameraViewerWidget with camera_ids: {camera_ids}")
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_ids = camera_ids
        self._cam_group_frame_worker = CamGroupFrameWorker(self._camera_ids)
        self._cam_group_frame_worker.cameras_connected_signal.connect(self.cameras_connected_signal.emit)
        if self._camera_ids is None:
            self._detect_available_cameras_push_button = self._create_detect_cameras_button()
            self._layout.addWidget(self._detect_available_cameras_push_button)
        else:
            self.connect_to_cameras()

    @property
    def controller_slot_dictionary(self):
        return self._cam_group_frame_worker.slot_dictionary


    def _handle_image_update(self, camera_id, image):
        self._video_label_dict[camera_id]["image_label"].setPixmap(QPixmap.fromImage(image))

    def _create_camera_view_grid_layout(self) -> dict:
        self._camera_view_grid_layout = QGridLayout()
        self._layout.addLayout(self._camera_view_grid_layout)

        video_label_dict = {}
        column_count = 0
        row_count = 0

        for camera_id in self._camera_ids:


            video_label_dict[camera_id] = {}
            video_label_dict[camera_id]["title_label"] = QLabel(f"Camera {camera_id} ")
            video_label_dict[camera_id]["image_label"] = QLabel(f"connecting... ")
            camera_layout = QVBoxLayout()
            camera_layout.addWidget(video_label_dict[camera_id]["title_label"])
            camera_layout.addWidget(video_label_dict[camera_id]["image_label"])

            self._camera_view_grid_layout.addLayout(camera_layout, row_count, column_count)


            # This section is for formatting the videos in the grid nicely - it fills out two columns and then moves on to the next row
            column_count += 1
            if column_count % 2 == 0:
                column_count = 0
                row_count += 1

        return video_label_dict

    def connect_to_cameras(self):
        logger.info("Connecting to cameras")
        self._detect_available_cameras_push_button.setText("Detecting Cameras...")
        self._detect_available_cameras_push_button.hide()
        if self._camera_ids is None:
            logger.info("No camera ids provided - detecting available cameras")
            self._camera_ids = detect_cameras().cameras_found_list
            self._cam_group_frame_worker.camera_ids = self._camera_ids

        self._cam_group_frame_worker.start()
        self._cam_group_frame_worker.ImageUpdate.connect(self._handle_image_update)

        self._video_label_dict = self._create_camera_view_grid_layout()

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
