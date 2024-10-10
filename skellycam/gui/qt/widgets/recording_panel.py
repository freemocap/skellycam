import logging

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget, QLabel, QVBoxLayout

from skellycam.gui import get_client, FastAPIClient
from skellycam.gui.qt.gui_state.gui_state import GUIState, get_gui_state

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

        buttons_layout = QHBoxLayout()
        self._start_recording_button = QPushButton("\U0001F534 Start Recording")
        self._start_recording_button.clicked.connect(self._start_recording)
        self._start_recording_button.setEnabled(True)

        self._stop_recording_button = QPushButton("Stop Recording")
        self._stop_recording_button.setEnabled(False)
        self._stop_recording_button.clicked.connect(self._stop_recording)
        buttons_layout.addWidget(self._start_recording_button)
        buttons_layout.addWidget(self._stop_recording_button)
        self._layout.addLayout(buttons_layout)

        self._recording_status_bar = self._create_recording_status_bar()
        self._layout.addLayout(self._recording_status_bar)

        self._gui_state: GUIState = get_gui_state()
        self._client: FastAPIClient = get_client()

    def update_widget(self):

        logger.gui(f"Updating {self.__class__.__name__}")
        if self._gui_state.record_frames_flag_status:
            self._handle_recording_in_progress()
        else:
            self._handle_no_recording_in_progress()

    def _handle_no_recording_in_progress(self):
        self._start_recording_button.setEnabled(True)
        self._stop_recording_button.setEnabled(False)
        self._start_recording_button.setText("\U0001F534 Start Recording")
        self._recording_status_label.setText("Recording Status:  - Not Recording -")
        if self._gui_state.recording_info:
            self._recording_folder_label.setText(
                f"Most Recent Recording Folder:  {self._gui_state.recording_info.recording_folder}")

    def _handle_recording_in_progress(self):
        self._start_recording_button.setEnabled(False)
        self._stop_recording_button.setEnabled(True)
        self._start_recording_button.setText("\U0001F534 Recording...")
        self._recording_status_label.setText(
            f"Recording Status: Recording! ({self._gui_state.frame_number} from {self._gui_state.number_of_cameras} cameras)")
        self._recording_folder_label.setText(
            f"Active Recording Folder:  {self._gui_state.recording_info.recording_folder}") if self._gui_state.recording_info else None

    def _start_recording(self):
        logger.gui("Starting Recording...")
        if self._gui_state.record_frames_flag_status:
            raise ValueError("Recording is already in progress! Button should be disabled.")
        self._client.start_recording()

    def _stop_recording(self):
        logger.gui("Stopping Recording.")
        if not self._gui_state.record_frames_flag_status:
            raise ValueError("Recording is not in progress! Button should be disabled.")
        self._client.stop_recording()

        self._start_recording_button.setEnabled(True)
        self._stop_recording_button.setEnabled(False)

    def _create_recording_status_bar(self) -> QHBoxLayout:
        recording_status_bar = QHBoxLayout()
        self._recording_status_label = QLabel("Recording Status:  - Not Recording -")
        recording_status_bar.addWidget(self._recording_status_label)
        self._recording_folder_label = QLabel("Active Recording Folder:  - None -")
        recording_status_bar.addWidget(self._recording_folder_label)
        self._frontend_framerate_label = QLabel("Frontend Median/Std FPS:  - None -")
        recording_status_bar.addWidget(self._frontend_framerate_label)
        return recording_status_bar
