from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from skellycam import logger
from skellycam.frontend.gui.widgets._update_widget_template import UpdateWidget
from skellycam.system.environment.default_paths import PATH_TO_SKELLY_CAM_LOGO_SVG


class Welcome(UpdateWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._initUI()
        self._parent_widget = parent
        self.updated.connect(self._parent_widget.update)
        self._session_started = False

        self._start_session_button.clicked.connect(lambda : self.emit_update(data={"session_started": True}))

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
        self._layout.addWidget(subtitle_text_label)
        subtitle_text_label.setText("The camera back-end for the FreeMoCap Project \U00002728")
        subtitle_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_text_label.setStyleSheet("""
                                            font-size: 24px;
                                           font-family: 'Dosis', sans-serif;
                                           color: #2b2e38;
                                            """)
        self._start_session_button = QPushButton("Start Session")
        self._layout.addWidget(self._start_session_button)
        self.resize(skellycam_logo_pixmap.width(), skellycam_logo_pixmap.height())


