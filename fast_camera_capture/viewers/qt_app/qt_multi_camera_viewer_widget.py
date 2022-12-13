import logging
from typing import Union, List

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget, QGridLayout, QVBoxLayout

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.opencv.group.camera_group import CameraGroup
from fast_camera_capture.viewers.qt_app.workers.cam.camworker import (
    CamGroupFrameWorker,
)

logger = logging.getLogger(__name__)


class QtMultiCameraViewerWidget(QWidget):
    def __init__(self,
                 camera_ids: List[Union[str, int]] = None,
                 parent=None):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        if camera_ids is None:
            camera_ids = detect_cameras().cameras_found_list
        self._camera_ids = camera_ids

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
        logger.info("Close event detected - closing camera group frame worker")
        self._cam_group_frame_worker.close()
        self.close()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from PyQt6.QtCore import QTimer

    import sys

    app = QApplication(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    main_window = QMainWindow()
    qt_multi_camera_viewer_widget = QtMultiCameraViewerWidget(parent=main_window)
    main_window.setCentralWidget(qt_multi_camera_viewer_widget)
    main_window.show()
    error_code = app.exec()
    qt_multi_camera_viewer_widget.close()

    sys.exit()
