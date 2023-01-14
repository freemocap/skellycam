from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SingleCameraViewWidget(QWidget):
    def __init__(self,
                 camera_id: str,
                 parent: QWidget = None):
        super().__init__(parent=parent)

        self._camera_id = camera_id

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._title_label_widget = QLabel(f"Camera {self._camera_id}")
        self._layout.addWidget(self._title_label_widget)
        self._title_label_widget.setStyleSheet("""
                           font-size: 18px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           """)
        self._title_label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label_widget = QLabel("\U0001F4F8 Connecting... ")
        self._image_label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._image_label_widget)

    @property
    def camera_id(self):
        return self._camera_id

    @property
    def image_label_widget(self):
        return self._image_label_widget

    def show(self):
        super().show()
        self._image_label_widget.show()
        self._title_label_widget.show()

    def hide(self):
        super().hide()
        self._image_label_widget.hide()
        self._title_label_widget.hide()

    def close(self):
        self._image_label_widget.close()
        self._title_label_widget.close()
        super().close()
