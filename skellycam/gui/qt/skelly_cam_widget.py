import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget, )

from skellycam.gui import get_client
from skellycam.gui.client.fastapi_client import FastAPIClient
from skellycam.gui.gui_state import GUIState, get_gui_state
from skellycam.gui.qt.utilities.qt_label_strings import no_cameras_found_message_string
from skellycam.system.default_paths import CAMERA_WITH_FLASH_EMOJI_STRING, \
    SPARKLES_EMOJI_STRING

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """

class SkellyCamWidget(QWidget):
    gui_state_changed = Signal()

    def __init__(
            self,
            parent=None,
    ):
        super().__init__(parent=parent)

        self.client: FastAPIClient = get_client()
        self.gui_state: GUIState = get_gui_state()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._camera_grid_view = CameraViewGrid(parent=self)
        self._layout.addWidget(self._camera_grid_view)

        self.detect_available_cameras_push_button = self._create_detect_cameras_button()
        self._layout.addWidget(self.detect_available_cameras_push_button)

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
        self.detect_available_cameras_push_button.clicked.connect(self._no_cameras_found_label.hide)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)

    def _show_cameras_disconnected_message(self):
        logger.info("Showing `cameras disconnected` message")
        self._camera_grid_view.clear_camera_views()
        self._cameras_disconnected_label.show()
        self.detect_available_cameras_push_button.show()

    def _show_no_cameras_found_message(self):
        logger.info("Showing `no cameras found` message")
        self._camera_grid_view.clear_camera_views()
        self._no_cameras_found_label.show()
        self.detect_available_cameras_push_button.show()

    def detect_available_cameras(self):
        logger.info("Connecting to cameras")
        detect_cameras_response = self.client.detect_cameras()
        logger.debug(f"Received result from `detect_cameras` call: {detect_cameras_response}")
        self._camera_configs = detect_cameras_response.detected_cameras

    def disconnect_from_cameras(self):
        logger.info("Disconnecting from cameras")
        self._camera_grid_view.clear_camera_views()

    def connect_to_cameras(self):
        logger.info("Connecting to cameras")
        connect_to_cameras_response = self.client.connect_to_cameras()
        logger.debug(f"`connect_to_cameras` success: {connect_to_cameras_response.success}")
        self.gui_state.camera_configs = connect_to_cameras_response.connected_cameras
        self.gui_state.available_devices = connect_to_cameras_response.detected_cameras
        self.gui_state_changed.emit()

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



    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        # self._cam_group_frame_worker.close()
        self.close()
