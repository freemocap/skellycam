from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget


class FrameNumberSlider(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMaximum(0)

        self.label = QLabel(str(self.slider.value()))
        self.slider.valueChanged.connect(
            lambda: self.label.setText(str(self.slider.value()))
        )

        self._layout.addWidget(self.label)
        self._layout.addWidget(self.slider)

    def set_slider_range(self, num_frames):
        self.slider_max = num_frames - 1
        self.slider.setValue(0)
        self.slider.setMaximum(self.slider_max)
