import logging

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from skellycam.gui.gui_state import get_gui_state
from skellycam.gui.qt.skelly_cam_widget import (
    SkellyCamWidget,
)

logger = logging.getLogger(__name__)


class SkellyCamRecordButtonsPanel(QWidget):
    def __init__(
            self, skellycam_widget: SkellyCamWidget, parent=None
    ):
        super().__init__(parent=parent)

        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)

        self._layout = QVBoxLayout()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._button_layout = self._create_buttons()
        self._layout.addLayout(self._button_layout)

        self._skellycam_widget = skellycam_widget

        self._gui_state = get_gui_state()

    def _create_buttons(self):
        button_layout = QHBoxLayout()

        self._start_recording_button = QPushButton("\U0001F534 Start Recording")
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.hide()
        self._start_recording_button.clicked.connect(self._start_recording)
        button_layout.addWidget(self._start_recording_button)

        self._stop_recording_button = QPushButton("\U00002B1B Stop Recording")
        self._stop_recording_button.setEnabled(False)
        self._stop_recording_button.hide()
        self._stop_recording_button.clicked.connect(self._stop_recording)
        button_layout.addWidget(self._stop_recording_button)

        return button_layout

    def _show_buttons(self):
        self._start_recording_button.show()
        self._stop_recording_button.show()

    def _start_recording(self):
        logger.debug("Starting Recording")
        self._gui_state.is_recording = True
        self._start_recording_button.setEnabled(False)
        self._start_recording_button.setText("Recording...")
        self._stop_recording_button.setEnabled(True)

    def _stop_recording(self):
        logger.debug("Stopping Recording")
        self._gui_state.is_recording = False
        self._start_recording_button.setEnabled(True)
        self._start_recording_button.setText("\U0001F534 Start Recording")
        self._stop_recording_button.setEnabled(False)
