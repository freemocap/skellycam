import logging

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget, QLabel, QVBoxLayout

from skellycam.gui import get_client, FastAPIClient
from skellycam.gui.gui_state import get_gui_state, GUIState

logger = logging.getLogger(__name__)


class RecordingPanel(QWidget):
    def __init__(
            self, parent=None
    ):
        super().__init__(parent=parent)

        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._recording_button = self._create_button()
        self._layout.addWidget(self._recording_button)

        self._recording_status_bar = self._create_recording_status_bar()
        self._layout.addLayout(self._recording_status_bar)

        self._gui_state: GUIState = get_gui_state()
        self._client: FastAPIClient = get_client()

    def update(self):
        super().update()
        if self._gui_state.is_recording:
            self._recording_status_label.setText(
                f"Recording Status: Recording! ({self._gui_state.number_of_frames} from {self._gui_state.number_of_cameras} cameras)")
            self._recording_folder_label.setText(
                f"Active Recording Folder:  {self._gui_state.recording_info.recording_folder}")
        else:
            self._recording_status_label.setText("Recording Status:  - Not Recording -")
            self._recording_folder_label.setText(
                f"Most Recent Recording Folder:  {self._gui_state.recording_info.recording_folder}")

    def _create_button(self) -> QPushButton:
        recording_button = QPushButton("\U0001F534 Start Recording")
        recording_button.setStyleSheet("background-color: #29696a")
        recording_button.setEnabled(True)
        recording_button.clicked.connect(self._start_recording)
        return recording_button

    def _start_recording(self):
        logger.debug("Starting Recording")
        self._client.start_recording()
        self._gui_state.is_recording = True
        self._recording_button.setText("\U0001F534 Stop Recording")
        self._recording_button.setStyleSheet("background-color: #860111 ")

    def _stop_recording(self):
        logger.debug("Stopping Recording")
        self._client.stop_recording()
        self._gui_state.is_recording = False
        self._recording_button.setStyleSheet("background-color: #29696a")
        self._recording_button.setText("\U0001F534 Start Recording")

    def _create_recording_status_bar(self) -> QHBoxLayout:
        recording_status_bar = QHBoxLayout()
        self._recording_status_label = QLabel("Recording Status:  - Not Recording -")
        recording_status_bar.addWidget(self._recording_status_label)
        self._recording_folder_label = QLabel("Active Recording Folder:  - None -")
        recording_status_bar.addWidget(self._recording_folder_label)
        return recording_status_bar
