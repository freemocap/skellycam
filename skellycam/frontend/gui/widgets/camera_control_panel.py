from PySide6.QtWidgets import QVBoxLayout, QPushButton

from skellycam.data_models.request_response_update import Request
from skellycam.frontend.gui.widgets._update_widget_template import UpdateWidget
from skellycam.frontend.gui.utilities.qt_strings import DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT, \
    CONNECT_TO_CAMERAS_BUTTON_TEXT, CLOSE_CAMERAS_BUTTON_TEXT


class CameraControlPanelView(UpdateWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()

        self._detect_available_cameras_button = QPushButton(self.tr(DETECT_AVAILABLE_CAMERAS_BUTTON_TEXT))
        self._connect_to_cameras = QPushButton(self.tr(CONNECT_TO_CAMERAS_BUTTON_TEXT))
        self._close_cameras_button = QPushButton(self.tr(CLOSE_CAMERAS_BUTTON_TEXT))

        self.initUI()

    def initUI(self):
        self._layout.addWidget(self._close_cameras_button)
        self._close_cameras_button.setEnabled(False)

        self._layout.addWidget(self._detect_available_cameras_button)
        self._detect_available_cameras_button.setEnabled(False)
        self._connect_buttons()

    def _connect_buttons(self):
        self._detect_available_cameras_button.clicked.connect(lambda:
                                                              self.emit_message(Request(
                                                                  message_type=MessageTypes.DETECT_AVAILABLE_CAMERAS)))
        self._connect_to_cameras.clicked.connect(lambda:
                                                 self.emit_message(Request(
                                                     message_type=MessageTypes.CONNECT_TO_CAMERAS)))
        self._close_cameras_button.clicked.connect(
            lambda: self.emit_message(Request(message_type=MessageTypes.CLOSE_CAMERAS)))
