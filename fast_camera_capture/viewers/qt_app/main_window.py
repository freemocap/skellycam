from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QMainWindow, QWidget, QGridLayout, QVBoxLayout

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.viewers.qt_app.workers.cam.camworker import (
    CamGroupFrameWorker,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._layout = QVBoxLayout()
        self._central_widget.setLayout(self._layout)

        self._camera_ids = detect_cameras().cameras_found_list
        self._cam_group_frame_worker = CamGroupFrameWorker(self._camera_ids)
        self._cam_group_frame_worker.start()
        self._cam_group_frame_worker.ImageUpdate.connect(self._handle_image_update)

        self._video_label_dict = self._create_camera_view_grid_layout()

    def _handle_image_update(self, camera_id, image):
        self._video_label_dict[camera_id].setPixmap(QPixmap.fromImage(image))

    def _create_camera_view_grid_layout(self) -> dict:
        self._camera_view_grid_layout = QGridLayout()
        self._layout.addLayout(self._camera_view_grid_layout)

        video_label_dict = {}
        column_count = 0
        row_count = 0

        for camera_id in self._camera_ids:

            video_label_dict[camera_id] = QLabel(f"Camera {camera_id}")

            self._camera_view_grid_layout.addWidget(video_label_dict[camera_id], row_count, column_count)

            # This section is for formatting the videos in the grid nicely - it fills out two columns and then moves on to the next row
            column_count += 1
            if column_count % 2 == 0:
                column_count = 0
                row_count += 1

        return video_label_dict

    def closeEvent(self, event):
        self._cam_group_frame_worker.close()
