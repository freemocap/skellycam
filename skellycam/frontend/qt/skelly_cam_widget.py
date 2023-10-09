import logging
from typing import Dict

import cv2
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton

from skellycam.data_models.camera_config import CameraConfig
from skellycam.frontend.qt.utilities.qt_label_strings import no_cameras_found_message_string
from skellycam.frontend.qt.widgets.single_camera_view_widget import SingleCameraViewWidget
from skellycam.system.environment.default_paths import MAGNIFYING_GLASS_EMOJI_STRING, CAMERA_WITH_FLASH_EMOJI_STRING

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 2
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 5


class SkellyCamWidget(QWidget):
    cameras_connected_signal = Signal()
    camera_group_created_signal = Signal(dict)
    incoming_camera_configs_signal = Signal(dict)
    videos_saved_to_this_folder_signal = Signal(str)

    def __init__(
            self,
            parent=None,
    ):

        logger.info(
            f"Initializing QtMultiCameraViewerWidget with camera_ids")

        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_views_layout = QHBoxLayout()
        self._camera_landscape_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_landscape_grid_layout)
        self._camera_portrait_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_portrait_grid_layout)
        self._layout.addLayout(self._camera_views_layout)

        self._detect_available_cameras_push_button = self._create_detect_cameras_button()
        self._layout.addWidget(self._detect_available_cameras_push_button)

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

        # self._layout.addStretch()

    @property
    def detect_available_cameras_push_button(self):
        return self._detect_available_cameras_push_button

    def _show_cameras_disconnected_message(self):
        logger.info("Showing `cameras disconnected` message")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
        self._cameras_disconnected_label.show()
        self._detect_available_cameras_push_button.show()

    def _show_no_cameras_found_message(self):
        logger.info("Showing `no cameras found` message")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
        self._no_cameras_found_label.show()
        self._detect_available_cameras_push_button.show()

    def _create_camera_view_widgets_and_add_them_to_grid_layout(self) -> dict:

        camera_config_dictionary = {}
        dictionary_of_single_camera_view_widgets = {}
        landscape_camera_number = -1
        portrait_camera_number = -1
        for camera_id, camera_config in camera_config_dictionary.items():

            single_camera_view = SingleCameraViewWidget(camera_id=camera_id,
                                                        camera_config=camera_config,
                                                        parent=self)

            if self._get_landscape_or_portrait(camera_config) == "landscape":
                landscape_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(landscape_camera_number),
                                                        MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_landscape_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            elif self._get_landscape_or_portrait(camera_config) == "portrait":
                portrait_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(portrait_camera_number),
                                                        MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_portrait_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            dictionary_of_single_camera_view_widgets[camera_id] = single_camera_view

        return dictionary_of_single_camera_view_widgets

    def _create_detect_cameras_button(self):
        detect_available_cameras_push_button = QPushButton(
            f"Detect Available Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{MAGNIFYING_GLASS_EMOJI_STRING}")
        detect_available_cameras_push_button.hasFocus()
        detect_available_cameras_push_button.setStyleSheet("""
                                                            border-width: 2px;
                                                           font-size: 42px;
                                                           border-radius: 10px;
                                                           """)
        detect_available_cameras_push_button.setProperty("recommended_next", True)

        return detect_available_cameras_push_button

    def _reset_detect_available_cameras_button(self):
        self._detect_available_cameras_push_button.setText("Detect Available Cameras")
        self._detect_available_cameras_push_button.setEnabled(True)

    def _get_landscape_or_portrait(self, camera_config: CameraConfig) -> str:
        if (
                camera_config.rotate_video_cv2_code == cv2.ROTATE_90_CLOCKWISE
                or camera_config.rotate_video_cv2_code == cv2.ROTATE_90_COUNTERCLOCKWISE
        ):
            return "portrait"

        return "landscape"

    def _clear_camera_grid_view(self, dictionary_of_single_camera_view_widgets: Dict[str, SingleCameraViewWidget]):
        if dictionary_of_single_camera_view_widgets is None:
            logger.info("No camera view widgets to clear")
            return

        logger.info("Clearing camera layout dictionary")
        try:
            for camera_id, single_camera_view_widget in dictionary_of_single_camera_view_widgets.items():
                single_camera_view_widget.close()
                self._camera_portrait_grid_layout.removeWidget(single_camera_view_widget)
                self._camera_landscape_grid_layout.removeWidget(single_camera_view_widget)
        except Exception as e:
            logger.error(f"Error clearing camera layout dictionary: {e}")
            raise e

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self.close()
