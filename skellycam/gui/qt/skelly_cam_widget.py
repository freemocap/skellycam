import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget, )

from skellycam.gui.qt.client.fastapi_client import FastAPIClient
from skellycam.gui.qt.widgets.camera_views.camera_grid_view import CameraViewGrid
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
            client: FastAPIClient,
            parent=None,
    ):
        super().__init__(parent=parent)
        self._client = client

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.recording_panel = RecordingPanel(parent=self, client=self._client)
        self._layout.addWidget(self.recording_panel)

        self.camera_view_grid = CameraViewGrid(parent=self)
        self._layout.addWidget(self.camera_view_grid)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)


    def detect_available_cameras(self):
        logger.gui("Connecting to cameras")
        self._client.detect_cameras()

    def connect_to_cameras(self):
        logger.gui("Connecting to cameras")
        if self._gui_state.user_selected_camera_configs:
            self.apply_settings_to_cameras()
        else:
            self._client.detect_and_connect_to_cameras()

    def close_cameras(self):
        logger.gui("Closing cameras")
        self._client.close_cameras()
        self.camera_view_grid.clear_camera_views()

    def apply_settings_to_cameras(self):
        logger.gui("Applying settings to cameras")
        self._client.apply_settings_to_cameras(camera_configs=self._)

    def closeEvent(self, event):
        logger.gui("Close event detected - closing camera group frame worker")
        self.close()
