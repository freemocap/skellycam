from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget

from skellycam.frontend.gui.utilities.qt_strings import DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT, \
    CONNECT_TO_CAMERAS_BUTTON_TEXT, CLOSE_CAMERAS_BUTTON_TEXT

CONTROL_PANEL_BUTTON_STYLESHEET = """
        QPushButton{
        border: 2px solid darkgreen;
        border-width: 2px;
        font-size: 15px;
        }
        """


class CameraControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._initUI()

    def _initUI(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.detect_available_cameras_button = QPushButton(self.tr(DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT))
        self.connect_to_cameras_button = QPushButton(self.tr(CONNECT_TO_CAMERAS_BUTTON_TEXT))
        self.connect_to_cameras_button.setEnabled(False)
        self.close_cameras_button = QPushButton(self.tr(CLOSE_CAMERAS_BUTTON_TEXT))
        self.close_cameras_button.setEnabled(False)
        self._layout.addWidget(self.detect_available_cameras_button)
        self._layout.addWidget(self.connect_to_cameras_button)
        self._layout.addWidget(self.close_cameras_button)
        self.setStyleSheet(CONTROL_PANEL_BUTTON_STYLESHEET)
        self._update_button_styles()

    def handle_cameras_detected(self):
        self.connect_to_cameras_button.setEnabled(True)
        self._update_button_styles()

    def handle_cameras_connected(self):
        self.close_cameras_button.setEnabled(True)
        self._update_button_styles()

    def handle_cameras_closed(self):
        self.close_cameras_button.setEnabled(False)
        self._update_button_styles()

    def _update_button_styles(self):

        self.detect_available_cameras_button.setStyleSheet(CONTROL_PANEL_BUTTON_STYLESHEET)
        self.connect_to_cameras_button.setStyleSheet(CONTROL_PANEL_BUTTON_STYLESHEET)
        self.close_cameras_button.setStyleSheet(CONTROL_PANEL_BUTTON_STYLESHEET)

        if not self.connect_to_cameras_button.isEnabled():
            self.detect_available_cameras_button.setStyleSheet("border: 2px solid pink;")
        elif not self.close_cameras_button.isEnabled():
            self.connect_to_cameras_button.setStyleSheet("border: 2px solid pink;")
