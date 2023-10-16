from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap, Qt
from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton

from skellycam.frontend.gui.widgets._update_widget_template import UpdateWidget
from skellycam.system.environment.default_paths import PATH_TO_SKELLY_CAM_LOGO_PNG, CAMERA_WITH_FLASH_EMOJI_STRING, \
    SPARKLES_EMOJI_STRING


class WelcomeView(UpdateWidget):
    session_started = Signal()
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._initUI()

    def _initUI(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        skellycam_logo_label = QLabel(self)
        self._layout.addWidget(skellycam_logo_label)
        skellycam_logo_pixmap = QPixmap(PATH_TO_SKELLY_CAM_LOGO_PNG)
        skellycam_logo_pixmap = skellycam_logo_pixmap.scaledToWidth(300)
        skellycam_logo_label.setPixmap(skellycam_logo_pixmap)
        skellycam_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skellycam_text_label = QLabel(self)
        self._layout.addWidget(skellycam_text_label)
        skellycam_text_label.setText("Welcome to Skelly Cam!")
        skellycam_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skellycam_text_label.setStyleSheet("""
                                            font-size: 54px;
                                           font-family: 'Dosis', sans-serif;
                                           color: #1b1e28;
                                            """)
        subtitle_text_label = QLabel(self)

        subtitle_text_label.setText("The camera back-end for the FreeMoCap Project")
        subtitle_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_text_label.setStyleSheet("""
                                            font-size: 24px;
                                           font-family: 'Dosis', sans-serif;
                                           color: #2b2e38;
                                            """)
        self._layout.addWidget(subtitle_text_label)

        self._create_start_session_button()
        self._layout.addWidget(self._start_session_button)
        self._layout.addStretch()

    def _create_start_session_button(self):
        self._start_session_button = QPushButton(
            f"Begin Session {CAMERA_WITH_FLASH_EMOJI_STRING}{SPARKLES_EMOJI_STRING}")
        self._start_session_button.hasFocus()
        self._start_session_button.setStyleSheet("""
                            border-width: 2px;
                           font-size: 42px;
                           border-radius: 10px;
                           width: 50%;
                           """)
        self._start_session_button.clicked.connect(self._start_session_button_clicked)

    def _start_session_button_clicked(self):
        self.hide()
        self.session_started.emit()

