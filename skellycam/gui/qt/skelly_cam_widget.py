import logging

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

    def update(self):
        super().update()
        self.recording_panel.update()
        self.camera_view_grid.update()

    def detect_available_cameras(self):
        logger.info("Connecting to cameras")
        self._client.detect_cameras()

    def connect_to_cameras(self):
        logger.info("Connecting to cameras")
        self._client.connect_to_cameras()

    def close_cameras(self):
        logger.info("Closing cameras")
        self._client.close_cameras()
        self.camera_view_grid.clear_camera_views()

    def apply_settings_to_cameras(self):
        logger.info("Applying settings to cameras")
        self._client.apply_settings_to_cameras(camera_configs=self._gui_state.camera_configs)

    def closeEvent(self, event):
        logger.info("Close event detected - closing camera group frame worker")
        self.close()
