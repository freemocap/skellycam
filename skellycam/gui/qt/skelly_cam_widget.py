import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget, )

from skellycam.gui import get_client
from skellycam.gui.client.fastapi_client import FastAPIClient
from skellycam.gui.gui_state import GUIState, get_gui_state
from skellycam.gui.qt.widgets.camera_grid_view import CameraViewGrid
from skellycam.gui.qt.widgets.recording_panel import RecordingPanel

logger = logging.getLogger(__name__)

title_label_style_string = """
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """


class SkellyCamWidget(QWidget):
    devices_detected = Signal()
    cameras_connected = Signal()
    cameras_closed = Signal()
    recording_started = Signal()
    recording_stopped = Signal
    new_frames_available = Signal()

    def __init__(
            self,
            parent=None,
    ):
        super().__init__(parent=parent)

        self._client: FastAPIClient = get_client()
        self._gui_state: GUIState = get_gui_state()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.recording_panel = RecordingPanel(parent=self)
        self._layout.addWidget(self.recording_panel)

        self.camera_view_grid = CameraViewGrid(parent=self)
        self._layout.addWidget(self.camera_view_grid)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)
        self._layout.addStretch()

    def detect_available_cameras(self):
        logger.info("Connecting to cameras")
        detect_cameras_response = self._client.detect_cameras()
        logger.debug(f"Received result from `detect_cameras` call: {detect_cameras_response}")
        self._gui_state.available_devices = detect_cameras_response.available_cameras
        self.devices_detected.emit()

    def connect_to_cameras(self):
        logger.info("Connecting to cameras")
        connect_to_cameras_response = self._client.connect_to_cameras()
        logger.debug(f"`connect_to_cameras` success: {connect_to_cameras_response.success}")
        self._gui_state.camera_configs = connect_to_cameras_response.connected_cameras
        self._gui_state.available_devices = connect_to_cameras_response.detected_cameras
        self.cameras_connected.emit()
        self.devices_detected.emit()

    def close_cameras(self):
        logger.info("Closing cameras")
        self._client.close_cameras()
        self.camera_view_grid.clear_camera_views()
        self.cameras_closed.emit()

    def apply_settings_to_cameras(self):
        logger.info("Applying settings to cameras")
        self._client.apply_settings_to_cameras(camera_configs=self._gui_state.camera_configs)
        self.cameras_connected.emit()

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        # self._cam_group_frame_worker.close()
        self.close()
