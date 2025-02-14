import logging
from typing import Optional

from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget, QLabel, QVBoxLayout, QLineEdit

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.qt_gui.qt.widgets.recording_control_panel.audio_record_panel import AudioRecorderWidget

logger = logging.getLogger(__name__)


class RecordingPanel(QWidget):
    def __init__(
            self,
            parent=None
    ):
        super().__init__(parent=parent)
        self._recording_info: Optional[RecordingInfo] = None
        self._initUI()


    def _initUI(self):
        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        buttons_layout = QHBoxLayout()
        self.start_recording_button = QPushButton("\U0001F534 Start Recording")
        self.start_recording_button.setEnabled(True)
        self.start_recording_button.clicked.connect(self.handle_recording_in_progress)

        self.stop_recording_button = QPushButton("Stop Recording")
        self.stop_recording_button.setEnabled(False)
        self.stop_recording_button.clicked.connect(self.handle_no_recording_in_progress)

        buttons_layout.addWidget(self.start_recording_button)
        buttons_layout.addWidget(self.stop_recording_button)

        self._layout.addLayout(buttons_layout)

        session_nametag_layout = QHBoxLayout()
        session_nametag_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.session_nametag_label = QLabel('Enter optional nametag here:')  
        self.session_nametag = QLineEdit()
        self.session_nametag.setFixedWidth(250)

        session_nametag_layout.addWidget(self.session_nametag_label)
        session_nametag_layout.addWidget(self.session_nametag)
        session_nametag_layout.addStretch(1)
        self._layout.addLayout(session_nametag_layout)
        self._recording_status_bar = self._create_recording_status_bar()
        self._layout.addLayout(self._recording_status_bar)

    @Slot(object)
    def handle_new_recording_info(self, recording_info: RecordingInfo):
        self._recording_info = recording_info
        self.handle_recording_in_progress()

    def handle_recording_in_progress(self):
        self.start_recording_button.setEnabled(False)
        self.stop_recording_button.setEnabled(True)
        self.start_recording_button.setText("\U0001F534 Recording...")
        self._recording_status_label.setText(
            f"Recording Status: Recording in progress!")
        
        recording_tag = self.session_nametag.text().strip()


        if self._recording_info:
            self._recording_folder_label.setText(
                f"Active Recording Folder:  {self._recording_info.recording_folder}")
            
        


    def handle_no_recording_in_progress(self):
        self.start_recording_button.setEnabled(True)
        self.stop_recording_button.setEnabled(False)
        self.start_recording_button.setText("\U0001F534 Start Recording")
        self._recording_status_label.setText("Recording Status:  - Not Recording -")
        if self._recording_info:
            self._recording_folder_label.setText(
                f"Most Recent Recording Folder:  {self._recording_info.recording_folder}")




    def _create_recording_status_bar(self) -> QHBoxLayout:
        recording_status_bar = QHBoxLayout()
        self.audio_recording_panel = AudioRecorderWidget()
        recording_status_bar.addWidget(self.audio_recording_panel)
        self._recording_status_label = QLabel("Recording Status:  - Not Recording -")
        recording_status_bar.addWidget(self._recording_status_label)
        self._recording_folder_label = QLabel("Active Recording Folder:  - None -")
        recording_status_bar.addWidget(self._recording_folder_label)
        self._frontend_framerate_label = QLabel("Frontend Median/Std FPS:  - None -")
        recording_status_bar.addWidget(self._frontend_framerate_label)
        return recording_status_bar
