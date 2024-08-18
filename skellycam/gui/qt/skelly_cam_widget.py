import logging
from typing import Dict, List, Union, Optional

import cv2
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget, QHBoxLayout,
)

from skellycam.api.client.fastapi_client import get_client, FastAPIClient
from skellycam.core.cameras.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.detection.camera_device_info import AvailableDevices
from skellycam.gui.gui_state import GUIState, get_gui_state
from skellycam.gui.qt.utilities.qt_label_strings import no_cameras_found_message_string
from skellycam.gui.qt.widgets.single_camera_view_widget import SingleCameraViewWidget
from skellycam.system.default_paths import CAMERA_WITH_FLASH_EMOJI_STRING, \
    SPARKLES_EMOJI_STRING

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 2
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 5


class SkellyCamWidget(QWidget):
    gui_state_changed = Signal()

    def __init__(
            self,
            get_new_synchronized_videos_folder_callable: callable,
            camera_ids: List[Union[str, int]] = None,
            parent=None,
    ):

        super().__init__(parent=parent)

        self.client: FastAPIClient = get_client()
        self.gui_state: [GUIState] = get_gui_state()

        self._get_new_synchronized_videos_folder_callable = get_new_synchronized_videos_folder_callable

        self._detect_cameras_worker = None
        self._dictionary_of_single_camera_view_widgets = None


        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_views_layout = QHBoxLayout()
        self._camera_landscape_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_landscape_grid_layout)
        self._camera_portrait_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_portrait_grid_layout)
        self._layout.addLayout(self._camera_views_layout)

        self._camera_configs: Optional[CameraConfigs] = None
        self._available_devices: Optional[AvailableDevices] = None

        self.detect_available_cameras_push_button = self._create_detect_cameras_button()
        self._layout.addWidget(self.detect_available_cameras_push_button)

        self._cameras_disconnected_label = QLabel(" - No Cameras Connected - ")
        self._layout.addWidget(self._cameras_disconnected_label)
        self._cameras_disconnected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cameras_disconnected_label.setStyleSheet(title_label_style_string)
        self._cameras_disconnected_label.hide()
        # self._cam_group_frame_worker.cameras_closed_signal.connect(self._show_cameras_disconnected_message)

        self._no_cameras_found_label = QLabel(no_cameras_found_message_string)
        self._layout.addWidget(self._no_cameras_found_label)
        self._no_cameras_found_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._no_cameras_found_label.setStyleSheet(title_label_style_string)
        self._no_cameras_found_label.hide()
        self.detect_available_cameras_push_button.clicked.connect(self._no_cameras_found_label.hide)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)




    def _show_cameras_disconnected_message(self):
        logger.info("Showing `cameras disconnected` message")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
        self._cameras_disconnected_label.show()
        self.detect_available_cameras_push_button.show()

    def _show_no_cameras_found_message(self):
        logger.info("Showing `no cameras found` message")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
        self._no_cameras_found_label.show()
        self.detect_available_cameras_push_button.show()

    def _create_camera_view_widgets_and_add_them_to_grid_layout(self, camera_config_dictionary: Dict[
        str, CameraConfig]) -> dict:

        logger.info(
            f"Creating camera view grid layout for camera config dictionary: {camera_config_dictionary}"
        )

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

    def detect_available_cameras(self):
        logger.info("Connecting to cameras")
        detect_cameras_response = self.client.detect_cameras()
        logger.debug(f"Received result from `detect_cameras` call: {detect_cameras_response}")
        self._camera_configs = detect_cameras_response.detected_cameras



    def disconnect_from_cameras(self):
        logger.info("Disconnecting from cameras")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)


    def _create_detect_cameras_button(self):
        detect_available_cameras_push_button = QPushButton(
            f"Connect To Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{SPARKLES_EMOJI_STRING}")
        detect_available_cameras_push_button.clicked.connect(self.connect_to_cameras)
        detect_available_cameras_push_button.clicked.connect(detect_available_cameras_push_button.hide)
        detect_available_cameras_push_button.hasFocus()
        detect_available_cameras_push_button.setStyleSheet("""
                                                            border-width: 2px;
                                                           font-size: 42px;
                                                           border-radius: 10px;
                                                           """)
        detect_available_cameras_push_button.setProperty("recommended_next", True)

        return detect_available_cameras_push_button

    def connect_to_cameras(self):
        logger.info("Connecting to cameras")
        connect_to_cameras_response = self.client.connect_to_cameras()
        logger.debug(f"Received result from `connect_to_cameras` call: {connect_to_cameras_response}")
        self.gui_state.camera_configs = connect_to_cameras_response.connected_cameras
        self.gui_state.available_devices = connect_to_cameras_response.detected_cameras
        self.gui_state_changed.emit()


    @Slot(str, QImage, dict)
    def _handle_image_update(self, camera_id: str, q_image: QImage, frame_diagnostics_dictionary: Dict):
        self._dictionary_of_single_camera_view_widgets[camera_id].handle_image_update(q_image=q_image,
                                                                                      frame_diagnostics_dictionary=frame_diagnostics_dictionary)

    def update_camera_configs(self, camera_config_dictionary):
        logger.info(f"Updating camera configs: {camera_config_dictionary}")

        if self._dictionary_of_single_camera_view_widgets is not None:
            logger.info("Camera view widgets already exist - clearing them from  the camera grid view layout")
            self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
            self._dictionary_of_single_camera_view_widgets = self._create_camera_view_widgets_and_add_them_to_grid_layout(
                camera_config_dictionary=camera_config_dictionary)

        for camera_id, camera_config in camera_config_dictionary.items():
            if camera_config.use_this_camera:
                self._dictionary_of_single_camera_view_widgets[camera_id].show()
                self._dictionary_of_single_camera_view_widgets[camera_id].show()
            else:
                self._dictionary_of_single_camera_view_widgets[camera_id].hide()
                self._dictionary_of_single_camera_view_widgets[camera_id].hide()

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
        # self._cam_group_frame_worker.close()
        self.close()


