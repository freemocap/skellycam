import logging
from pathlib import Path
from typing import List, Union

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from skellycam import CameraConfig
from skellycam.qt_gui.workers.camera_group_frame_worker import CamGroupFrameWorker
from skellycam.qt_gui.workers.detect_cameras_worker import DetectCamerasWorker

logger = logging.getLogger(__name__)


class QtMultiCameraViewerWidget(QWidget):
    cameras_connected_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    incoming_camera_configs_signal = pyqtSignal(dict)

    def __init__(
        self,
        camera_ids: List[Union[str, int]] = None,
        session_folder_path: Union[str, Path] = None,
        parent=None,
    ):

        logger.info(
            f"Initializing QtMultiCameraViewerWidget with camera_ids: {camera_ids}"
        )

        self._session_folder_path = session_folder_path
        self._camera_view_layout = None
        self._camera_config_dicationary = None
        self._detect_cameras_worker = None
        self._camera_layout_dictionary = None

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
        try:
            self._camera_layout_dictionary[camera_id]["image_label_widget"].setPixmap(
                QPixmap.fromImage(image)
            )
        except Exception as e:
            logger.error(f"Problem in _handle_image_update for Camera {camera_id}: {e}")

    def _create_camera_view_grid_layout(self, camera_config_dictionary: dict) -> dict:

        if self._camera_layout_dictionary is not None:
            logger.info(
                "Camera layout dictionary already exists - returning existing dictionary"
            )
            return self._camera_layout_dictionary

        logger.info(
            f"Creating camera view grid layout for camera config dictionary: {camera_config_dictionary}"
        )
        camera_view_layout = QHBoxLayout()
        self._layout.addLayout(camera_view_layout)

        self._portrait_grid_layout = QGridLayout()
        camera_view_layout.addLayout(self._portrait_grid_layout)

        self._landscape_grid_layout = QGridLayout()
        camera_view_layout.addLayout(self._landscape_grid_layout)

        camera_layout_dictionary = {}
        for camera_id, camera_config in camera_config_dictionary.items():
            camera_layout_dictionary[camera_id] = {}

            camera_layout = QVBoxLayout()
            camera_layout_dictionary[camera_id]["layout"] = camera_layout
            camera_layout_dictionary[camera_id][
                "orientation"
            ] = self._get_landscape_or_portrait(camera_config)
            camera_layout_dictionary[camera_id]["title_label_widget"] = QLabel(
                f"Camera {camera_id}"
            )
            camera_layout_dictionary[camera_id]["title_label_widget"].setStyleSheet(
                """
                                                                                    font-size: 18px;
                                                                                    font-weight: bold;
                                                                                    font-family: "Dosis", sans-serif;
                                                                                    """
            )
            camera_layout_dictionary[camera_id]["image_label_widget"] = QLabel(
                "\U0001F4F8 Connecting... "
            )
            camera_layout_dictionary[camera_id]["title_label_widget"].setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            camera_layout.addWidget(
                camera_layout_dictionary[camera_id]["title_label_widget"]
            )
            camera_layout.addWidget(
                camera_layout_dictionary[camera_id]["image_label_widget"]
            )

        self._arrange_camera_layouts(camera_layout_dictionary)
        return camera_layout_dictionary

    def _arrange_camera_layouts(self, camera_layout_dictionary: dict):
        primary_grid_count = np.ceil(np.sqrt(len(camera_layout_dictionary))) - 1

        landscape_column_count = -1
        landscape_row_count = -1
        portrait_column_count = -1
        portrait_row_count = -1

        for camera_id, single_camera_layout_dict in camera_layout_dictionary.items():
            camera_layout = single_camera_layout_dict["layout"]

            # self._remove_camera_layout_from_grid_layouts(camera_layout,
            #                                              [self._landscape_grid_layout, self._portrait_grid_layout])

            if camera_layout_dictionary[camera_id]["orientation"] == "landscape":
                landscape_column_count += 1
                if landscape_column_count % primary_grid_count == 0:
                    landscape_column_count = 0
                    landscape_row_count += 1
                logger.info(
                    f"Adding camera {camera_id} to landscape grid layout at {landscape_column_count}, {landscape_row_count}"
                )
                self._landscape_grid_layout.addLayout(
                    camera_layout, landscape_row_count, landscape_column_count
                )
            else:
                portrait_column_count += 1
                if portrait_row_count % primary_grid_count == 0:
                    portrait_column_count = 0
                    portrait_row_count += 1
                    logger.info(
                        f"Adding camera {camera_id} to portrait grid layout at {portrait_column_count}, {portrait_row_count}"
                    )
                self._portrait_grid_layout.addLayout(
                    camera_layout, portrait_row_count, portrait_column_count
                )

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

    def _start_camera_group_frame_worker(self, camera_ids):
        logger.info(f"Starting camera group frame worker with camera_ids: {camera_ids}")
        self._cam_group_frame_worker.camera_ids = camera_ids
        self._camera_layout_dictionary = self._create_camera_view_grid_layout(
            camera_config_dictionary=self._cam_group_frame_worker.camera_config_dictionary
        )
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
        detect_available_cameras_push_button.setStyleSheet("""
                                                            border-width: 2px;
                                                           font-size: 42px;
                                                           border-radius: 10px;
                                                           """ )


        return detect_available_cameras_push_button

    def _create_cam_group_frame_worker(self):
        cam_group_frame_worker = CamGroupFrameWorker(
            camera_ids=self._camera_ids, session_folder_path=self._session_folder_path
        )

        cam_group_frame_worker.cameras_connected_signal.connect(
            self._handle_cameras_connected
        )

        cam_group_frame_worker.camera_group_created_signal.connect(
            self.camera_group_created_signal.emit
        )

        self.incoming_camera_configs_signal.connect(self._update_camera_configs)
        return cam_group_frame_worker

    def _handle_detected_cameras(self, camera_ids):
        logger.info(f"Detected cameras: {camera_ids}")
        self._camera_ids = camera_ids
        self._detect_available_cameras_push_button.setText(
            f"Connecting to Cameras {camera_ids}..."
        )
        self._start_camera_group_frame_worker(self._camera_ids)

    def _handle_cameras_connected(self):
        self.cameras_connected_signal.emit()
        self._reset_detect_available_cameras_button()

    def _reset_detect_available_cameras_button(self):
        self._detect_available_cameras_push_button.setText("Detect Available Cameras")
        self._detect_available_cameras_push_button.setEnabled(True)
        self._detect_available_cameras_push_button.setStyleSheet("font-size: 36px;")

    def _update_camera_configs(self, camera_config_dictionary):
        # self._create_camera_view_grid_layout(camera_config_dictionary=camera_config_dictionary)
        for camera_id, camera_config in camera_config_dictionary.items():
            if camera_config.use_this_camera:
                self._camera_layout_dictionary[camera_id]["title_label_widget"]
                self._camera_layout_dictionary[camera_id]["image_label_widget"].show()
            else:
                self._camera_layout_dictionary[camera_id]["title_label_widget"].hide()
                self._camera_layout_dictionary[camera_id]["image_label_widget"].hide()

        self._cam_group_frame_worker.update_camera_group_configs(
            camera_config_dictionary=camera_config_dictionary
        )

    def _get_landscape_or_portrait(self, camera_config: CameraConfig) -> str:
        if (
            camera_config.rotate_video_cv2_code == cv2.ROTATE_90_CLOCKWISE
            or camera_config.rotate_video_cv2_code == cv2.ROTATE_90_COUNTERCLOCKWISE
        ):
            return "portrait"

        return "landscape"

    def _remove_camera_layout_from_grid_layouts(self, camera_layout, grid_layouts):
        if not isinstance(grid_layouts, list):
            grid_layouts = [grid_layouts]
        for grid_layout in grid_layouts:
            index = grid_layout.indexOf(camera_layout)
            if index != -1:
                logger.debug(
                    f"Removing camera layout {camera_layout}from grid layout {grid_layout} at index {index}"
                )
                grid_layout.takeAt(index)
            else:
                logger.debug(
                    f"Camera layout {camera_layout} not found in grid layout {grid_layout}"
                )


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    qt_multi_camera_viewer_widget = QtMultiCameraViewerWidget()
    main_window.setCentralWidget(qt_multi_camera_viewer_widget)
    main_window.show()
    error_code = app.exec()
    qt_multi_camera_viewer_widget.close()

    sys.exit()
