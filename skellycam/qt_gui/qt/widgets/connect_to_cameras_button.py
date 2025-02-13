from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from skellycam.system.default_paths import CAMERA_WITH_FLASH_EMOJI_STRING, SPARKLES_EMOJI_STRING


class ConnectToCamerasButton(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.button = self._create_button()
        self._layout.addWidget(self.button)

    def _create_button(self):
        button = QPushButton(
            f"Connect To Cameras {CAMERA_WITH_FLASH_EMOJI_STRING}{SPARKLES_EMOJI_STRING}")

        button.hasFocus()
        button.setStyleSheet("""
                            border-width: 2px;
                            font-size: 42px;
                            border-radius: 10px;
                            padding: 10px;
                            border-color: #AA00FF;
                            """)
        return button
