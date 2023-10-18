from typing import Dict

import cv2
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QWidget

from skellycam import logger
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.frontend.gui.utilities.qt_strings import no_cameras_found_message_string
from skellycam.frontend.gui.widgets.cameras.single_camera import SingleCameraView

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 2
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 5


class CameraGrid(QWidget):
    cameras_connected_signal = Signal()
    camera_group_created_signal = Signal(dict)
    incoming_camera_configs_signal = Signal(dict)
    videos_saved_to_this_folder_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._camera_configs = {}
        self._single_cameras = {}

        self._initUI()

        # self._layout.addStretch()

    def _initUI(self):

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._camera_views_layout = QHBoxLayout()
        self._camera_landscape_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_landscape_grid_layout)
        self._camera_portrait_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_portrait_grid_layout)
        self._layout.addLayout(self._camera_views_layout)
        self._cameras_disconnected_label = QLabel(" - No Cameras Connected - ")
        self._layout.addWidget(self._cameras_disconnected_label)
        self._cameras_disconnected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cameras_disconnected_label.setStyleSheet(title_label_style_string)
        self._cameras_disconnected_label.hide()
        self._no_cameras_found_label = QLabel(no_cameras_found_message_string)
        self._layout.addWidget(self._no_cameras_found_label)
        self._no_cameras_found_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._no_cameras_found_label.setStyleSheet(title_label_style_string)
        self._no_cameras_found_label.hide()
        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)

    def update_camera_grid(self, available_cameras: Dict[str, CameraDeviceInfo]):
        self._camera_configs = {}
        for camera_id, camera_info in available_cameras.items():

            self._camera_configs[camera_id] = CameraConfig(camera_id=camera_id,
                                                           framerate=camera_info.available_framerates[-1])

            if camera_id not in self._single_cameras:
                self._single_cameras[camera_id] = SingleCameraView(camera_config=self._camera_configs[camera_id],
                                                                   parent=self)
            else:
                self._single_cameras[camera_id].update_camera_config(camera_config=self._camera_configs[camera_id])

            self._add_cameras_to_layout()

    def _add_cameras_to_layout(self):
        landscape_camera_number = -1
        portrait_camera_number = -1
        for camera_id, single_camera in self._single_cameras.items():
            if camera_id not in self._camera_configs:
                single_camera.close()
                self._layout.removeWidget(single_camera)

            if self._get_landscape_or_portrait(self._camera_configs[camera_id]) == "landscape":
                landscape_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(landscape_camera_number),
                                                        MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_landscape_grid_layout.addWidget(self._single_cameras[camera_id], grid_row, grid_column)

            elif self._get_landscape_or_portrait(self._camera_configs[camera_id]) == "portrait":
                portrait_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(portrait_camera_number),
                                                        MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_portrait_grid_layout.addWidget(self._single_cameras[camera_id], grid_row, grid_column)

    @staticmethod
    def _get_landscape_or_portrait(camera_config: CameraConfig) -> str:
        if (
                camera_config.rotate_video_cv2_code == cv2.ROTATE_90_CLOCKWISE
                or camera_config.rotate_video_cv2_code == cv2.ROTATE_90_COUNTERCLOCKWISE
        ):
            return "portrait"

        return "landscape"

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self.close()
