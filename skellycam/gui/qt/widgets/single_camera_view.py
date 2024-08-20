import base64
import sys
import time

import cv2
import numpy as np
from PySide6.QtCore import Qt, QByteArray, QBuffer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy


class EfficientQImageUpdater:
    def __init__(self):
        self.byte_array = QByteArray()
        self.buffer = QBuffer(self.byte_array)
        self.qimage = QImage()

    def update_image(self, base64_str: str) -> QImage:
        image_data = base64.b64decode(base64_str)
        self.buffer.setData(image_data)
        self.buffer.open(QBuffer.ReadOnly)
        self.qimage.loadFromData(self.buffer.data())
        self.buffer.close()
        return self.qimage


class SingleCameraViewWidget(QWidget):
    def __init__(self, camera_id, camera_config, parent=None):
        super().__init__(parent=parent)

        self._camera_id = camera_id
        self._camera_config = camera_config

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._camera_name_string = f"Camera {self._camera_id}"
        self._title_label_widget = QLabel(self._camera_name_string, parent=self)
        self._layout.addWidget(self._title_label_widget)
        self._title_label_widget.setStyleSheet("""
                           font-size: 12px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           color: #000000;
                           """)

        self._title_label_widget.setAlignment(Qt.AlignCenter)

        self._image_label_widget = QLabel("\U0001F4F8 Connecting... ")
        self._image_label_widget.setStyleSheet("border: 1px solid;")
        self._image_label_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_label_widget.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._image_label_widget)

        self.image_updater = EfficientQImageUpdater()
        self._current_pixmap = QPixmap()

    @property
    def camera_id(self):
        return self._camera_id

    @property
    def image_label_widget(self):
        return self._image_label_widget

    def update_image(self, base64_str: str):
        q_image = self.image_updater.update_image(base64_str)
        self._current_pixmap = QPixmap.fromImage(q_image)
        self.update_pixmap()

    def resizeEvent(self, event):
        self.update_pixmap()
        super().resizeEvent(event)

    def update_pixmap(self):
        if not self._current_pixmap.isNull():
            scaled_pixmap = self._current_pixmap.scaled(
                self._image_label_widget.size() * 0.95,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._image_label_widget.setPixmap(scaled_pixmap)


def generate_dummy_data(num_frames: int, width: int, height: int) -> list:
    dummy_data = []
    for _ in range(num_frames):
        # Create a dummy image
        image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        # Convert the image to JPEG and then to base64
        _, buffer = cv2.imencode('.jpg', image)
        base64_str = base64.b64encode(buffer).decode('utf-8')
        dummy_data.append(base64_str)
    return dummy_data


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create the widget
    widget = SingleCameraViewWidget(camera_id=1, camera_config=None)
    widget.show()

    # Generate 100 frames of dummy data
    dummy_frames = generate_dummy_data(num_frames=100, width=1920, height=1080)

    while widget.isVisible():
        # Simulate updating the widget with dummy data
        for i, frame in enumerate(dummy_frames):
            widget.update_image(frame)
            app.processEvents()
            time.sleep(0.01)  # Simulate a delay between frames

    sys.exit(app.exec())
