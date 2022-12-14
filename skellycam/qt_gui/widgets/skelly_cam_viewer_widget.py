import logging
import time
from pathlib import Path
from typing import List, Union

import cv2
import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt
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
from skellycam.qt_gui.qt_utils.clear_layout import clear_layout
from skellycam.qt_gui.qt_utils.qt_label_strings import no_cameras_found_message_string
from skellycam.qt_gui.workers.camera_group_frame_worker import CamGroupFrameWorker
from skellycam.qt_gui.workers.detect_cameras_worker import DetectCamerasWorker

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """


class SkellyCamViewerWidget(QWidget):
    cameras_connected_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    incoming_camera_configs_signal = pyqtSignal(dict)
    new_recording_video_folder_created_signal = pyqtSignal(str)

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
        self._camera_config_dicationary = None
        self._detect_cameras_worker = None
        self._camera_layout_dictionary = None

        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_view_layout = QHBoxLayout()
        self._layout.addLayout(self._camera_view_layout)

        self._camera_ids = camera_ids
        self._cam_group_frame_worker = self._create_cam_group_frame_worker()
        self._cam_group_frame_worker.cameras_closed_signal.connect(self._show_cameras_disconnected_message)

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



        self._layout.addStretch()




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

    def _handle_image_update(self, camera_id, image):
        try:
            self._camera_layout_dictionary[camera_id]["image_label_widget"].setPixmap(
                QPixmap.fromImage(image)
            )
        except Exception as e:
            logger.error(f"Problem in _handle_image_update for Camera {camera_id}: {e}")

    def _show_cameras_disconnected_message(self):
        logger.info("Showing `cameras disconnected` message")
        self._clear_camera_layout_dictionary(self._camera_layout_dictionary)
        self._cameras_disconnected_label.show()
        self._detect_available_cameras_push_button.show()

    def _show_no_cameras_found_message(self):
        logger.info("Showing `no cameras found` message")
        self._clear_camera_layout_dictionary(self._camera_layout_dictionary)
        self._no_cameras_found_label.show()
        self._detect_available_cameras_push_button.show()

    def _create_camera_view_grid_layout(self, camera_config_dictionary: dict) -> dict:

        if self._camera_layout_dictionary is not None:
            self._clear_camera_layout_dictionary(self._camera_layout_dictionary)

        logger.info(
            f"Creating camera view grid layout for camera config dictionary: {camera_config_dictionary}"
        )

        self._portrait_grid_layout = QGridLayout()
        self._camera_view_layout.addLayout(self._portrait_grid_layout)

        self._landscape_grid_layout = QGridLayout()
        self._camera_view_layout.addLayout(self._landscape_grid_layout)

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
            camera_layout_dictionary[camera_id]["title_label_widget"].setStyleSheet(title_label_style_string)

            camera_layout_dictionary[camera_id]["image_label_widget"] = QLabel("\U0001F4F8 Connecting... ")
            camera_layout_dictionary[camera_id]["image_label_widget"].setAlignment(Qt.AlignmentFlag.AlignCenter)

            camera_layout_dictionary[camera_id]["title_label_widget"].setAlignment(Qt.AlignmentFlag.AlignCenter)

            camera_layout.addWidget(camera_layout_dictionary[camera_id]["title_label_widget"])
            camera_layout.addWidget(camera_layout_dictionary[camera_id]["image_label_widget"])

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
        self._camera_layout_dictionary = self._create_camera_view_grid_layout(
            camera_config_dictionary=self._cam_group_frame_worker.camera_config_dictionary
        )
        self._cam_group_frame_worker.start()
        self._cam_group_frame_worker.ImageUpdate.connect(self._handle_image_update)

    def disconnect_from_cameras(self):
        logger.info("Disconnecting from cameras")
        self._clear_camera_layout_dictionary(self._camera_layout_dictionary)
        self._cam_group_frame_worker.close()

    def pause(self):
        self._cam_group_frame_worker.pause()

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self._cam_group_frame_worker.close()
        self.close()

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
            session_folder_path=self._session_folder_path,
            new_recording_video_folder_created_signal=self.new_recording_video_folder_created_signal,
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

    def _reset_detect_available_cameras_button(self):
        self._detect_available_cameras_push_button.setText("Detect Available Cameras")
        self._detect_available_cameras_push_button.setEnabled(True)


    def _update_camera_configs(self, camera_config_dictionary):
        # self._create_camera_view_grid_layout(camera_config_dictionary=camera_config_dictionary)
        for camera_id, camera_config in camera_config_dictionary.items():
            if camera_config.use_this_camera:
                self._camera_layout_dictionary[camera_id]["title_label_widget"].show()
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

    def _clear_camera_layout_dictionary(self, camera_layout_dictionary: dict):
        logger.info("Clearing camera layout dictionary")
        try:
            for camera_id, camera_layout_dictionary in camera_layout_dictionary.items():
                clear_layout(camera_layout_dictionary["layout"])
        except Exception as e:
            logger.error(f"Error clearing camera layout dictionary: {e}")


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
