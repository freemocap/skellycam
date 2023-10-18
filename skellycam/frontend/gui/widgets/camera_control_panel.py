from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QLabel

from skellycam.frontend.gui.utilities.qt_strings import DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT, \
    CONNECT_TO_CAMERAS_BUTTON_TEXT, CLOSE_CAMERAS_BUTTON_TEXT


class CameraControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.detect_available_cameras_button = QPushButton(self.tr(DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT))
        self.connect_to_cameras_button = QPushButton(self.tr(CONNECT_TO_CAMERAS_BUTTON_TEXT))
        self.close_cameras_button = QPushButton(self.tr(CLOSE_CAMERAS_BUTTON_TEXT))

        self._layout.addWidget(self.detect_available_cameras_button)
        self._layout.addWidget(self.connect_to_cameras_button)
        self._layout.addWidget(self.close_cameras_button)

        self.setStyleSheet("""
        QPushButton{
        border-width: 2px;
        font-size: 15px;
        }
        """)


