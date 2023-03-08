import logging
from typing import Dict, List

import cv2
from PyQt6.QtCore import pyqtSignal, Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget, QHBoxLayout,
)

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.gui.qt.utilities.qt_label_strings import no_cameras_found_message_string
from skellycam.gui.qt.widgets.single_camera_view_widget import SingleCameraViewWidget
from skellycam.gui.qt.workers.camera_group_thread_worker import CamGroupThreadWorker
from skellycam.gui.qt.workers.detect_cameras_worker import DetectCamerasWorker
from skellycam.system.environment.default_paths import MAGNIFYING_GLASS_EMOJI_STRING, CAMERA_WITH_FLASH_EMOJI_STRING

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """


class SkellyCamWidget(QWidget):
    cameras_connected_signal = pyqtSignal()
    new_camera_configs_signal = pyqtSignal(dict)
    incoming_camera_configs_signal = pyqtSignal(dict)
    videos_saved_to_this_folder_signal = pyqtSignal(str)

    def __init__(
            self,
            get_new_synchronized_videos_folder: callable,
            parent=None,
    ):

        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._get_new_synchronized_videos_folder = get_new_synchronized_videos_folder

        self._detect_cameras_worker = None
        self._dictionary_of_single_camera_view_widgets = None
        self._cam_group_frame_worker = None

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
        self.cameras_connected_signal.connect(self._cameras_disconnected_label.hide)

        self._no_cameras_found_label = QLabel(no_cameras_found_message_string)
        self._layout.addWidget(self._no_cameras_found_label)
        self._no_cameras_found_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._no_cameras_found_label.setStyleSheet(title_label_style_string)
        self._no_cameras_found_label.hide()
        self.cameras_connected_signal.connect(self._no_cameras_found_label.hide)
        self._detect_available_cameras_push_button.clicked.connect(self._no_cameras_found_label.hide)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)

    @property
    def cameras_connected(self):
        return self._cam_group_frame_worker.cameras_connected

    @property
    def is_recording(self):
        return self._cam_group_frame_worker.is_recording

    @property
    def detect_available_cameras_push_button(self):
        return self._detect_available_cameras_push_button

    def start_recording(self):
        assert self._cam_group_frame_worker is not None, "`self._cam_group_frame_worker` is None, cannot start recording"
        self._cam_group_frame_worker.start_recording()

    def stop_recording(self):
        assert self._cam_group_frame_worker is not None, "`self._cam_group_frame_worker` is None, cannot stop recording"
        self._cam_group_frame_worker.stop_recording()

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

    def _create_camera_view_widgets_and_add_them_to_grid_layout(self, camera_configs: Dict[
        str, CameraConfig]) -> dict:

        logger.info(
            f"Creating camera view grid layout for camera config dictionary: {camera_configs}"
        )

        dictionary_of_single_camera_view_widgets = {}
        landscape_camera_number = -1
        portrait_camera_number = -1

        number_of_cameras = len(camera_configs)

        if number_of_cameras < 3:
            max_num_columns_for_landscape_camera_views = 1
        elif number_of_cameras < 6:
            max_num_columns_for_landscape_camera_views = 2
        else:
            max_num_columns_for_landscape_camera_views = 3

        max_num_columns_for_portrait_camera_views = 5

        for camera_id, camera_config in camera_configs.items():

            single_camera_view = SingleCameraViewWidget(camera_id=camera_id,
                                                        camera_config=camera_config,
                                                        parent=self)

            if self._get_landscape_or_portrait(camera_config) == "landscape":
                landscape_camera_number += 1

                divmod_whole, divmod_remainder = divmod(int(landscape_camera_number),
                                                        max_num_columns_for_landscape_camera_views)
                grid_row = divmod_whole
                grid_column = divmod_remainder

                self._camera_landscape_grid_layout.addWidget(single_camera_view, grid_row, grid_column)

            elif self._get_landscape_or_portrait(camera_config) == "portrait":
                portrait_camera_number += 1
                divmod_whole, divmod_remainder = divmod(int(portrait_camera_number),
                                                        max_num_columns_for_portrait_camera_views)
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

    def _start_camera_group_frame_worker(self, camera_ids: List[str], camera_configs: Dict[str, CameraConfig]):

        logger.info(f"Starting camera group frame worker with camera_ids: {camera_ids}")
        if self._cam_group_frame_worker is not None:
            self._cam_group_frame_worker.close()
            del self._cam_group_frame_worker

        self._cam_group_frame_worker = self._create_cam_group_frame_worker(
            camera_ids=camera_ids,
            camera_configs=camera_configs,
        )
        self._dictionary_of_single_camera_view_widgets = self._create_camera_view_widgets_and_add_them_to_grid_layout(
            camera_configs=camera_configs
        )
        self._cam_group_frame_worker.start()
        self._cam_group_frame_worker.new_image_signal.connect(self._handle_image_update)

    def _create_cam_group_frame_worker(self, camera_ids: List[str], camera_configs: Dict[str, CameraConfig]):
        cam_group_frame_worker = CamGroupThreadWorker(
            camera_ids=camera_ids,
            camera_configs=camera_configs,
            get_new_synchronized_videos_folder=self._get_new_synchronized_videos_folder,
        )

        cam_group_frame_worker.cameras_connected_signal.connect(
            self._handle_cameras_connected
        )

        cam_group_frame_worker.videos_saved_to_this_folder_signal.connect(
            self._handle_videos_saved_to_this_folder
        )

        cam_group_frame_worker.cameras_closed_signal.connect(self._show_cameras_disconnected_message)

        return cam_group_frame_worker

    def disconnect_from_cameras(self):
        logger.info("Disconnecting from cameras")
        self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
        self._cam_group_frame_worker.close()

    def _create_detect_cameras_button(self):
        detect_available_cameras_push_button = QPushButton(
            f"Detect Available Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{MAGNIFYING_GLASS_EMOJI_STRING}")
        detect_available_cameras_push_button.clicked.connect(self.detect_available_cameras)
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

    @pyqtSlot(str)
    def _handle_videos_saved_to_this_folder(self, folder_path: str):
        logger.debug(f"Emitting `videos_saved_to_this_folder_signal` with string: {folder_path}")
        self.videos_saved_to_this_folder_signal.emit(folder_path)

    @pyqtSlot(list)
    def _handle_detected_cameras(self, camera_ids: List[str]):
        if len(camera_ids) == 0:
            logger.info("No cameras detected")
            self._reset_detect_available_cameras_button()
            self._show_no_cameras_found_message()
            return

        logger.info(f"Detected cameras: {camera_ids}")
        self._detect_available_cameras_push_button.hide()

        self._detect_available_cameras_push_button.setText(
            f"Connecting to Cameras {camera_ids}..."
        )
        camera_configs = {camera_id: CameraConfig(camera_id=camera_id) for camera_id in camera_ids}
        self.new_camera_configs_signal.emit(camera_configs)
        self._start_camera_group_frame_worker(camera_ids=camera_ids,
                                              camera_configs=camera_configs)

    @pyqtSlot()
    def _handle_cameras_connected(self):
        self.cameras_connected_signal.emit()
        self._reset_detect_available_cameras_button()

    @pyqtSlot(dict)
    def _handle_image_update(self, latest_frames: Dict[str, FramePayload]):
        for camera_id, frame_payload in latest_frames.items():
            if frame_payload:
                self._dictionary_of_single_camera_view_widgets[camera_id].handle_image_update(
                    frame_payload=frame_payload)

    @pyqtSlot(dict)
    def update_camera_configs(self, camera_configs: Dict[str, CameraConfig]):
        logger.info(f"Updating camera configs: {camera_configs}")

        if self._dictionary_of_single_camera_view_widgets is not None:
            logger.info("Camera view widgets already exist - clearing them from  the camera grid view layout")
            self._clear_camera_grid_view(self._dictionary_of_single_camera_view_widgets)
            self._dictionary_of_single_camera_view_widgets = self._create_camera_view_widgets_and_add_them_to_grid_layout(
                camera_configs=camera_configs)

        for camera_id, camera_config in camera_configs.items():
            if camera_config.use_this_camera:
                self._dictionary_of_single_camera_view_widgets[camera_id].show()
                self._dictionary_of_single_camera_view_widgets[camera_id].show()
            else:
                self._dictionary_of_single_camera_view_widgets[camera_id].hide()
                self._dictionary_of_single_camera_view_widgets[camera_id].hide()

        self._cam_group_frame_worker.update_camera_configs(camera_configs=camera_configs)

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self._cam_group_frame_worker.close()
        self.close()


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    qt_multi_camera_viewer_widget = SkellyCamWidget()
    main_window.setCentralWidget(qt_multi_camera_viewer_widget)
    main_window.show()
    error_code = app.exec()
    qt_multi_camera_viewer_widget.close()

    sys.exit()
