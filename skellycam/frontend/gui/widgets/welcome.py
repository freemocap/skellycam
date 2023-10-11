from PySide6.QtGui import QPixmap, Qt
from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton

from skellycam.data_models.request_response import UpdateModel
from skellycam.frontend.gui.widgets._update_widget_template import UpdateWidget
from skellycam.system.environment.default_paths import PATH_TO_SKELLY_CAM_LOGO_SVG, MAGNIFYING_GLASS_EMOJI_STRING, \
    CAMERA_WITH_FLASH_EMOJI_STRING


class Welcome(UpdateWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._initUI()
        self._session_started = False



    def _initUI(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        skellycam_logo_label = QLabel(self)
        self._layout.addWidget(skellycam_logo_label)
        skellycam_logo_pixmap = QPixmap(PATH_TO_SKELLY_CAM_LOGO_SVG)
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

        subtitle_text_label.setText("The camera back-end for the FreeMoCap Project \U00002728")
        subtitle_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_text_label.setStyleSheet("""
                                            font-size: 24px;
                                           font-family: 'Dosis', sans-serif;
                                           color: #2b2e38;
                                            """)
        self._layout.addWidget(subtitle_text_label)

        self._create_start_session_button()
        self._layout.addWidget(self._start_session_button)

    def _create_start_session_button(self):
        self._start_session_button = QPushButton(
            f"Detect Available Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{MAGNIFYING_GLASS_EMOJI_STRING}")
        self._start_session_button.hasFocus()
        self._start_session_button.setStyleSheet("""
                            border-width: 2px;
                           font-size: 42px;
                           border-radius: 10px;
                           """)
        self._start_session_button.clicked.connect(lambda: self.emit_update(UpdateModel(data={"session_started": True},
                                                                                        source=self.name)))
