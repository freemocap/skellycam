import logging

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

from skellycam.frontend.qt.skelly_cam_widget import (
    SkellyCamWidget,
)

logger = logging.getLogger(__name__)


class SkellyCamControllerWidget(QWidget):
    def __init__(
            self, camera_viewer_widget: SkellyCamWidget, parent=None
    ):
        super().__init__(parent=parent)

        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)

        self._layout = QVBoxLayout()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._button_layout, self._button_dictionary = self._create_button_dictionary()
        self._layout.addLayout(self._button_layout)

        self._camera_viewer_widget = camera_viewer_widget
        self._camera_viewer_widget.cameras_connected_signal.connect(
            self._show_buttons
        )

    @property
    def stop_recording_button(self):
        return self._button_dictionary["stop_recording"]

    @property
    def start_recording_button(self):
        return self._button_dictionary["start_recording"]

    def _create_button_dictionary(self):
        button_layout = QHBoxLayout()

        button_dictionary = {}
        #
        # play_push_button = QPushButton("Play")
        # play_push_button.setEnabled(False)
        # play_push_button.clicked.connect(self._play_push_button_clicked)
        # play_push_button.hide()
        # button_layout.addWidget(play_push_button)
        # button_dictionary["play"] = play_push_button

        # pause_push_button = QPushButton("Pause")
        # pause_push_button.setEnabled(True)
        # pause_push_button.hide()
        # pause_push_button.clicked.connect(self._pause_push_button_clicked)
        # button_layout.addWidget(pause_push_button)
        # button_dictionary["pause"] = pause_push_button

        start_recording_push_button = QPushButton("\U0001F534 Start Recording")
        start_recording_push_button.setEnabled(True)
        start_recording_push_button.hide()

        button_layout.addWidget(start_recording_push_button)
        button_dictionary["start_recording"] = start_recording_push_button

        stop_recording_push_button = QPushButton("\U00002B1B Stop Recording")
        stop_recording_push_button.setEnabled(False)
        stop_recording_push_button.hide()
        button_layout.addWidget(stop_recording_push_button)
        button_dictionary["stop_recording"] = stop_recording_push_button

        return button_layout, button_dictionary

    def _show_buttons(self):
        for button in self._button_dictionary.values():
            button.show()

    def _play_push_button_clicked(self):
        logger.debug("Play button clicked")
        # self._button_dictionary["play"].setEnabled(False)
        # self._button_dictionary["pause"].setEnabled(True)
        self._button_dictionary["start_recording"].setEnabled(True)
        self._button_dictionary["stop_recording"].setEnabled(False)

    def _pause_push_button_clicked(self):
        logger.debug("Pause button clicked")
        # self._button_dictionary["play"].setEnabled(True)
        # self._button_dictionary["pause"].setEnabled(False)
        self._button_dictionary["start_recording"].setEnabled(False)
        self._button_dictionary["stop_recording"].setEnabled(False)

    def _start_recording_push_button_clicked(self):
        logger.debug("Start Recording button clicked")

    def _stop_recording_push_button_clicked(self):
        logger.debug("Stop Recording button clicked")
