from typing import Dict

import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QWidget

from skellycam.system.environment.get_logger import logger
from skellycam.frontend.gui.skellycam_widget.sub_widgets.central_widgets.camera_views.single_camera import \
    SingleCameraView
from skellycam.frontend.gui.utilities.qt_strings import no_cameras_found_message_string
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 2
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 5


class CameraGrid(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._initUI()
        self._camera_configs: Dict[CameraId, CameraConfig] = {}
        self._single_cameras: Dict[str, SingleCameraView] = {}

    def _initUI(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._create_camera_view_layouts()

        self._create_text_labels()

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)

    @Slot(MultiFramePayload)
    def handle_new_images(self, payload: MultiFramePayload):
        # logger.trace(f"Got new images Updating camera views")
        try:
            # cv2.imshow("wow", payload)
            for camera_id, frame in payload.frames.items():
                if camera_id in self._single_cameras.keys():
                    self._single_cameras[camera_id].handle_image_update(frame=frame)
                    # cv2.imshow(f"Camera {camera_id}", frame.image)
                else:
                    raise KeyError(f"Camera ID {camera_id} not found in camera grid")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            raise e

    def _create_camera_view_layouts(self):
        self._camera_views_layout = QHBoxLayout()
        self._camera_landscape_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_landscape_grid_layout)
        self._camera_portrait_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_portrait_grid_layout)
        self._layout.addLayout(self._camera_views_layout)

    def _create_text_labels(self):
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

    def update_camera_grid(self, camera_configs: Dict[CameraId, CameraConfig]):
        logger.info(f"Updating camera grid with cameras: {camera_configs.keys()}")
        self._camera_configs = camera_configs
        # self._handle_text_labels()
        self._close_vestigial_views()

        for camera_id, config in camera_configs.items():
            if camera_id not in self._single_cameras:
                self._single_cameras[camera_id] = SingleCameraView(camera_config=config,
                                                                   parent=self)

        self._add_cameras_to_layout()

    def _close_vestigial_views(self):
        for camera_id in list(self._single_cameras.keys()):
            if camera_id not in self._camera_configs.keys():
                self._single_cameras[camera_id].close()
                self._single_cameras.pop(camera_id)

    def _add_cameras_to_layout(self):
        landscape_cameras = [camera_id for camera_id, config in self._camera_configs.items() if
                             config.orientation == "landscape"]
        portrait_cameras = [camera_id for camera_id, config in self._camera_configs.items() if
                            config.orientation == "portrait"]

        landscape_camera_dimensions = self._calculate_grid_dimensions(len(landscape_cameras), self._camera_configs[
            landscape_cameras[0]].aspect_ratio) if landscape_cameras else (0, 0)
        portrait_camera_dims = self._calculate_grid_dimensions(len(portrait_cameras), self._camera_configs[
            portrait_cameras[0]].aspect_ratio) if portrait_cameras else (0, 0)

        for camera_number, camera_id in enumerate(landscape_cameras):
            grid_row, grid_column = divmod(camera_number, landscape_camera_dimensions[1])
            self._camera_landscape_grid_layout.addWidget(self._single_cameras[camera_id], grid_row, grid_column)

        for camera_number, camera_id in enumerate(portrait_cameras):
            grid_row, grid_column = divmod(camera_number, portrait_camera_dims[1])
            self._camera_portrait_grid_layout.addWidget(self._single_cameras[camera_id], grid_row, grid_column)

    def _calculate_grid_dimensions(self, num_cameras, aspect_ratio):
        if aspect_ratio > 1:  # Landscape mode
            grid_width = np.ceil(np.sqrt(num_cameras))
            grid_height = np.ceil(num_cameras / grid_width)
        else:  # Portrait mode
            grid_height = np.ceil(np.sqrt(num_cameras / aspect_ratio))
            grid_width = np.ceil(num_cameras / grid_height)

        return grid_height, grid_width

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self.close()

    def _handle_text_labels(self):
        if len(self._camera_configs) == 0:
            self._cameras_disconnected_label.show()
            self._no_cameras_found_label.show()
        else:
            self._cameras_disconnected_label.hide()
            self._no_cameras_found_label.hide()
