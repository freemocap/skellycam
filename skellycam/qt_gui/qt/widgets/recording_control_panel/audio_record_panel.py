from PySide6.QtWidgets import QApplication, QWidget, QComboBox, QCheckBox, QLabel, QHBoxLayout

from skellycam.system.device_detection.detect_microphone_devices import get_available_microphones


class AudioRecorderWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        # Checkbox for recording audio
        self.record_checkbox = QCheckBox("Record audio")
        self.record_checkbox.setChecked(True)

        # Dropdown for microphone selection
        self.mic_dropdown = QComboBox()
        self.mic_dropdown.addItem("default")
        self.mic_dropdown.setCurrentIndex(0)
        self.populate_mic_dropdown()


        # Add widgets to layout
        layout.addWidget(self.record_checkbox)
        layout.addWidget(QLabel("Select Microphone:"))
        layout.addWidget(self.mic_dropdown)

        self.setLayout(layout)

    @property
    def user_selected_mic_index(self) -> int:
        if not self.record_checkbox.isChecked():
            return -1
        return self.mic_dropdown.currentIndex()

    def populate_mic_dropdown(self):
        self.mic_dropdown.clear()

        mics = get_available_microphones()
        for mic_index, mic_name in mics.items():
            if mic_index == 0:
                self.mic_dropdown.addItem(f"0 - Default Microphone")
            else:
                self.mic_dropdown.addItem(f"{mic_index} - {mic_name}")
        self.mic_dropdown.setCurrentIndex(0)

if __name__ == "__main__":
    app = QApplication([])

    widget = AudioRecorderWidget()
    widget.show()

    app.exec()