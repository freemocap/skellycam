import logging

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget, )

from skellycam.gui.qt.widgets.recording_control_panel.recording_panel import RecordingPanel
from skellycam.skellycam_app.skellycam_app_state import SkellycamAppStateDTO
from skellycam.gui.qt.widgets.camera_widgets.camera_grid_view import CameraViewGrid

logger = logging.getLogger(__name__)


class SkellycamCameraPanel(QWidget):

    def __init__(
            self,
            parent=None,
    ):
        super().__init__(parent=parent)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.recording_panel = RecordingPanel(parent=self)
        self._layout.addWidget(self.recording_panel)

        self.camera_view_grid = CameraViewGrid(parent=self)
        self._layout.addWidget(self.camera_view_grid)

        self.sizePolicy().setHorizontalStretch(1)
        self.sizePolicy().setVerticalStretch(1)


    def closeEvent(self, event):
        logger.gui("Close event detected - closing camera group frame worker")
        self.close()

    def handle_new_app_state(self, app_state: SkellycamAppStateDTO):
        if app_state.record_frames_flag_status:
            # Change background to red
            self.camera_view_grid.setStyleSheet("background-color: red;")
        else:
            # Reset to default background color
            self.camera_view_grid.setStyleSheet("")
            self.recording_panel.handle_no_recording_in_progress()
