import base64
import logging
import sys
import time
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, QByteArray, QBuffer, QSize, QRect, QMutex, QMutexLocker
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QAction, QBrush
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy, QMenu

from skellycam.gui.qt.gui_state.models.camera_framerate_stats import CameraFramerateStats
import logging
logger = logging.getLogger(__name__)
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

        self._image_label_widget = QLabel(f"\U0001F4F8 Camera {self._camera_id} Connecting... ")
        self._image_label_widget.setStyleSheet("border: 1px solid;")
        self._image_label_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._image_label_widget.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._image_label_widget)

        self._image_updater = EfficientQImageUpdater()
        self._current_pixmap = QPixmap()

        self._annotations_enabled = True
        self._mutex = QMutex()

        # Enable context menu on QLabel
        self._image_label_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._image_label_widget.customContextMenuRequested.connect(self._show_context_menu)

    @property
    def camera_id(self):
        return self._camera_id

    @property
    def image_label_widget(self):
        return self._image_label_widget

    @property
    def image_size(self) -> QSize:
        with QMutexLocker(self._mutex):
            return self._current_pixmap.size()

    def update_image(self,
                     base64_str: str):
        logger.gui(f"Updating {self.__class__.__name__} with image for camera {self.camera_id}")
        with QMutexLocker(self._mutex):
            q_image = self._image_updater.update_image(base64_str)
            self._current_pixmap = QPixmap.fromImage(q_image)
            # if self._annotations_enabled:
                # self._annotate_pixmap()
            self.update_pixmap()
        logger.gui(f"Successfully updated {self.__class__.__name__} with image for camera {self.camera_id}")

    def _annotate_pixmap(self, framerate_stats: Optional[CameraFramerateStats], recording: bool = False):
        logger.gui(f"Annotating pixmap for camera {self.camera_id}")
        painter = QPainter(self._current_pixmap)
        pixmap_width = self._current_pixmap.width()
        pixmap_height = self._current_pixmap.height()
        font_size = min(pixmap_width, pixmap_height) // 30  # Adjust the divisor for preferred size

        painter.setFont(QFont('Arial', font_size))

        # Draw semi-transparent background without a border
        painter.setPen(Qt.NoPen)

        background_rect = QRect(5, 5, int(pixmap_width * .55), 100)
        painter.setBrush(QBrush(QColor(255, 255, 255, 100)))  # Semi-transparent white background
        painter.drawRect(background_rect)

        # Draw text
        # Restore painter state for drawing text
        if recording:
            painter.setPen(QColor(255, 0, 0))  # Red color
        else:
            painter.setPen(QColor(0, 0, 255))  # Blue color
        painter.drawText(10, 20, f"Recording Frames? {recording}")
        painter.drawText(10, 40, f"CameraId: {self.camera_id}")
        if framerate_stats:
            painter.drawText(10, 60, f"Frame#: {framerate_stats.frame_number}")
            if framerate_stats.duration_stats:
                painter.drawText(10, 80, f"Frame Duration (mean/std): {framerate_stats.duration_mean_std_ms_str}")
                painter.drawText(10, 100, f"Mean FPS: {framerate_stats.fps_mean_str}")
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        with QMutexLocker(self._mutex):
            self.update_pixmap()

    def update_pixmap(self):
        if not self._current_pixmap.isNull():
            logger.gui(f"Updating pixmap for camera {self.camera_id}")
            scaled_pixmap = self._current_pixmap.scaled(
                self._image_label_widget.size() * 0.95,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._image_label_widget.setPixmap(scaled_pixmap)

    def _toggle_annotations(self):
        self._annotations_enabled = not self._annotations_enabled

    def _show_context_menu(self, pos):
        context_menu = QMenu(self)
        toggle_action = QAction("Toggle Annotations", self)
        toggle_action.triggered.connect(lambda: self._toggle_annotations())
        context_menu.addAction(toggle_action)
        context_menu.exec_(self._image_label_widget.mapToGlobal(pos))


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
