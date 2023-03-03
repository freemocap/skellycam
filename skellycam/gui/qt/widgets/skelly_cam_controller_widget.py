import logging

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from skellycam.gui.qt.skelly_cam_widget import (
    SkellyCamWidget,
)

logger = logging.getLogger(__name__)


class SkellyCamControllerWidget(QWidget):
    def __init__(
            self, skelly_cam_widget: SkellyCamWidget, parent=None
    ):
        super().__init__(parent=parent)

        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)

        self._layout = QVBoxLayout()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._create_buttons()

        self._skelly_cam_widget = skelly_cam_widget
        self._skelly_cam_widget.cameras_connected_signal.connect(
            self._show_buttons
        )

        self._start_recording_push_button.clicked.connect(self._skelly_cam_widget.start_recording)
        self._stop_recording_push_button.clicked.connect(self._skelly_cam_widget.stop_recording)

    @property
    def stop_recording_button(self):
        return self._stop_recording_push_button

    @property
    def start_recording_button(self):
        return self._start_recording_push_button

    def _create_buttons(self):
        button_layout = QHBoxLayout()
        self._layout.addLayout(button_layout)
        self._start_recording_push_button = QPushButton("\U0001F534 Start Recording")
        self._start_recording_push_button.setEnabled(True)
        self._start_recording_push_button.hide()
        self._start_recording_push_button.clicked.connect(
            self._start_recording_push_button_clicked
        )
        button_layout.addWidget(self._start_recording_push_button)

        self._stop_recording_push_button = QPushButton("\U00002B1B Stop Recording")
        self._stop_recording_push_button.setEnabled(False)
        self._stop_recording_push_button.hide()
        self._stop_recording_push_button.clicked.connect(
            self._stop_recording_push_button_clicked
        )
        button_layout.addWidget(self._stop_recording_push_button)

    def _show_buttons(self):
        self._start_recording_push_button.show()
        self._stop_recording_push_button.show()

    def _play_push_button_clicked(self):
        logger.debug("Play button clicked")

        self._start_recording_push_button.setEnabled(True)
        self._stop_recording_push_button.setEnabled(False)

    def _pause_push_button_clicked(self):
        logger.debug("Pause button clicked")
        self._start_recording_push_button.setEnabled(False)
        self._stop_recording_push_button.setEnabled(False)

    def _start_recording_push_button_clicked(self):
        logger.debug("Start Recording button clicked")
        if self._skelly_cam_widget.cameras_connected:
            self._start_recording_push_button.setEnabled(False)
            self._start_recording_push_button.setText("\U0001F534 \U000021BB Recording...")
            self._stop_recording_push_button.setEnabled(True)

    def _stop_recording_push_button_clicked(self):
        logger.debug("Stop Recording button clicked")
        self._start_recording_push_button.setEnabled(True)
        self._start_recording_push_button.setText("\U0001F534 Start Recording")
        self._stop_recording_push_button.setEnabled(False)


    def set_calibration_recordings_button_label(self, boolean: bool):
        if boolean:
            self._start_recording_push_button.setText("\U0001F534 \U0001F4D0 Start Recording (Calibration Videos)")
        else:
            self._start_recording_push_button.setText("\U0001F534 Start Recording")
