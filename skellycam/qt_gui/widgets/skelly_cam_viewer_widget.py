import logging
from typing import Dict, List, Union

import cv2
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget, QHBoxLayout,
)

from skellycam import CameraConfig
from skellycam.qt_gui.utilities.qt_label_strings import no_cameras_found_message_string
from skellycam.qt_gui.widgets.single_camera_view_widget import SingleCameraViewWidget
from skellycam.qt_gui.workers.camera_group_frame_worker import CamGroupFrameWorker
from skellycam.qt_gui.workers.detect_cameras_worker import DetectCamerasWorker

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """

MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS = 2
MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS = 3

class SkellyCamViewerWidget(QWidget):
    cameras_connected_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    incoming_camera_configs_signal = pyqtSignal(dict)
    videos_saved_to_this_folder_signal = pyqtSignal(str)

    def __init__(
            self,
            get_new_synchronized_videos_folder_callable: callable,
            camera_ids: List[Union[str, int]] = None,
            parent=None,
    ):

        logger.info(
            f"Initializing QtMultiCameraViewerWidget with camera_ids: {camera_ids}"
        )

        self._get_new_synchronized_videos_folder_callable = get_new_synchronized_videos_folder_callable

        self._camera_config_dicationary = None
        self._detect_cameras_worker = None
        self._dictionary_of_single_camera_view_widgets = None

        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_views_layout = QHBoxLayout()
        self._camera_landscape_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_landscape_grid_layout)
        self._camera_portrait_grid_layout = QGridLayout()
        self._camera_views_layout.addLayout(self._camera_portrait_grid_layout)
        self._layout.addLayout(self._camera_views_layout)

        self._camera_ids = camera_ids
        self._cam_group_frame_worker = self._create_cam_group_frame_worker()

        self._detect_available_cameras_push_button = self._create_detect_cameras_button()
        self._layout.addWidget(self._detect_available_cameras_push_button)

        self._cameras_disconnected_label = QLabel(" - No Cameras Connected - ")
        self._layout.addWidget(self._cameras_disconnected_label)
        self._cameras_disconnected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cameras_disconnected_label.setStyleSheet(title_label_style_string)
        self._cameras_disconnected_label.hide()
        self.cameras_connected_signal.connect(self._cameras_disconnected_label.hide)
        self._cam_group_frame_worker.cameras_closed_signal.connect(self._show_cameras_disconnected_message)

        self._no_cameras_found_label = QLabel(no_cameras_found_message_string)
        self._layout.addWidget(self._no_cameras_found_label)
        self._no_cameras_found_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._no_cameras_found_label.setStyleSheet(title_label_style_string)
        self._no_cameras_found_label.hide()
        self.cameras_connected_signal.connect(self._no_cameras_found_label.hide)
        self._detect_available_cameras_push_button.clicked.connect(self._no_cameras_found_label.hide)

        # self._layout.addStretch()

    @property
    def controller_slot_dictionary(self):
        return self._cam_group_frame_worker.slot_dictionary

    @property
    def camera_config_dicationary(self):
        return self._camera_config_dicationary

    @property
    def cameras_connected(self):
        return self._cam_group_frame_worker.cameras_connected

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
                divmod_whole, divmod_remainder = divmod(int(landscape_camera_number), MAX_NUM_ROWS_FOR_LANDSCAPE_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_landscape_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            elif self._get_landscape_or_portrait(camera_config) == "portrait":
                portrait_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(portrait_camera_number), MAX_NUM_COLUMNS_FOR_PORTRAIT_CAMERA_VIEWS)
                grid_row = divmod_whole
                grid_column = divmod_remainder
                self._camera_portrait_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            dictionary_of_single_camera_view_widgets[camera_id] = single_camera_view

        return dictionary_of_single_camera_view_widgets

    def detect_available_cameras(self):
        try:
            self.disconnect_from_cameras()
        except Exception as e:
            logger.error(f"Problem disconnecting from cameras: {e}")

        logger.info("Connecting to cameras")

        self._detect_available_cameras_push_button.setText("Detecting Cameras...")
        self._detect_available_cameras_push_button.setEnabled(False)
        self._cameras_disconnected_label.hide()

        self._detect_cameras_worker = DetectCamerasWorker()
        self._detect_cameras_worker.cameras_detected_signal.connect(
            self._handle_detected_cameras
        )
        self._detect_cameras_worker.start()

    def _start_camera_group_frame_worker(self, camera_ids):

        logger.info(f"Starting camera group frame worker with camera_ids: {camera_ids}")
        self._cam_group_frame_worker.camera_ids = camera_ids
        self._dictionary_of_single_camera_view_widgets = self._create_camera_view_widgets_and_add_them_to_grid_layout(
            camera_config_dictionary=self._cam_group_frame_worker.camera_config_dictionary
        )
        self._cam_group_frame_worker.start()
        self._cam_group_frame_worker.new_image_signal.connect(self._handle_image_update)

    def disconnect_from_cameras(self):
        logger.info("Disconnecting from cameras")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
        self._cam_group_frame_worker.close()

    def pause(self):
        self._cam_group_frame_worker.pause()

    def _create_detect_cameras_button(self):
        detect_available_cameras_push_button = QPushButton("Detect Available Cameras")
        detect_available_cameras_push_button.clicked.connect(self.detect_available_cameras)
        detect_available_cameras_push_button.hasFocus()
        detect_available_cameras_push_button.setStyleSheet("""
                                                            border-width: 2px;
                                                           font-size: 42px;
                                                           border-radius: 10px;
                                                           """)
        detect_available_cameras_push_button.setProperty("recommended_next", True)

        return detect_available_cameras_push_button

    def _create_cam_group_frame_worker(self):
        cam_group_frame_worker = CamGroupFrameWorker(
            camera_ids=self._camera_ids,
            get_new_synchronized_videos_folder_callable=self._get_new_synchronized_videos_folder_callable,
        )

        cam_group_frame_worker.cameras_connected_signal.connect(
            self._handle_cameras_connected
        )

        cam_group_frame_worker.camera_group_created_signal.connect(
            self.camera_group_created_signal.emit
        )

        cam_group_frame_worker.videos_saved_to_this_folder_signal.connect(
            self.videos_saved_to_this_folder_signal.emit
        )

        return cam_group_frame_worker

    def _handle_detected_cameras(self, camera_ids):
        if len(camera_ids) == 0:
            logger.info("No cameras detected")
            self._reset_detect_available_cameras_button()
            self._show_no_cameras_found_message()
            return

        logger.info(f"Detected cameras: {camera_ids}")
        self._detect_available_cameras_push_button.hide()
        self._camera_ids = camera_ids
        self._detect_available_cameras_push_button.setText(
            f"Connecting to Cameras {camera_ids}..."
        )
        self._start_camera_group_frame_worker(self._camera_ids)

    def _handle_cameras_connected(self):
        self.cameras_connected_signal.emit()
        self._reset_detect_available_cameras_button()

    def _handle_image_update(self, camera_id: str, q_image: QImage):
        self._dictionary_of_single_camera_view_widgets[camera_id].handle_image_update(q_image=q_image)

    def _reset_detect_available_cameras_button(self):
        self._detect_available_cameras_push_button.setText("Detect Available Cameras")
        self._detect_available_cameras_push_button.setEnabled(True)

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
        self._cam_group_frame_worker.close()
        self.close()


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    qt_multi_camera_viewer_widget = SkellyCamViewerWidget()
    main_window.setCentralWidget(qt_multi_camera_viewer_widget)
    main_window.show()
    error_code = app.exec()
    qt_multi_camera_viewer_widget.close()

    sys.exit()
