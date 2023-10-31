from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QWidget

from skellycam.frontend.gui.utilities.qt_strings import STOP_RECORDING_BUTTON_TEXT, START_RECORDING_BUTTON_TEXT


class RecordButtons(QWidget):
    def __init__(
            self,
            parent=None
    ):
        super().__init__(parent=parent)

        self._initUI()

    def _initUI(self):
        self.sizePolicy().setVerticalStretch(1)
        self.sizePolicy().setHorizontalStretch(1)
        self._layout = QVBoxLayout()
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._button_layout = self._create_buttons()
        self._layout.addLayout(self._button_layout)


    def _create_buttons(self) -> QHBoxLayout:
        button_layout = QHBoxLayout()

        self.start_recording_button = QPushButton(self.tr(START_RECORDING_BUTTON_TEXT))
        self.start_recording_button.setEnabled(True)
        self.start_recording_button.hide()

        button_layout.addWidget(self.start_recording_button)

        self.stop_recording_button = QPushButton(self.tr(STOP_RECORDING_BUTTON_TEXT))
        self.stop_recording_button.setEnabled(False)
        self.stop_recording_button.hide()
        button_layout.addWidget(self.stop_recording_button)
        return button_layout

    def show(self):
        super().show()
        self.start_recording_button.show()
        self.stop_recording_button.show()

    def hide(self):
        super().hide()
        self.start_recording_button.hide()
        self.stop_recording_button.hide()
