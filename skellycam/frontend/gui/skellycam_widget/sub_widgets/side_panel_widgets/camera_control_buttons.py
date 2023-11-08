from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget

from skellycam.frontend.gui.utilities.qt_strings import DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT, \
    CONNECT_TO_CAMERAS_BUTTON_TEXT, CLOSE_CAMERAS_BUTTON_TEXT, APPLY_CAMERA_SETTINGS_BUTTON_TEXT

CONTROL_PANEL_BUTTON_STYLESHEET = """
        QPushButton{
        border-width: 2px;
        font-size: 15px;
        }        
        """


class CameraControlButtons(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._initUI()

    def _initUI(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.close_cameras_button = QPushButton(self.tr(CLOSE_CAMERAS_BUTTON_TEXT))
        self.close_cameras_button.setEnabled(False)
        self._layout.addWidget(self.close_cameras_button)

        self.detect_available_cameras_button = QPushButton(self.tr(DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT))
        self.detect_available_cameras_button.setEnabled(False)
        self._layout.addWidget(self.detect_available_cameras_button)

        self.connect_to_cameras_button = QPushButton(self.tr(CONNECT_TO_CAMERAS_BUTTON_TEXT))
        self.connect_to_cameras_button.setEnabled(False)
        self._layout.addWidget(self.connect_to_cameras_button)

        self.apply_camera_settings_button = QPushButton(self.tr(APPLY_CAMERA_SETTINGS_BUTTON_TEXT))
        self.apply_camera_settings_button.setEnabled(False)
        self._layout.addWidget(self.apply_camera_settings_button)





        self.setStyleSheet(CONTROL_PANEL_BUTTON_STYLESHEET)

