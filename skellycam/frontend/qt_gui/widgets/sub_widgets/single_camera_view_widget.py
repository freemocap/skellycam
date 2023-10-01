import logging

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from skellycam.data_models.camera_config import CameraConfig

logger = logging.getLogger(__name__)


class SingleCameraViewWidget(QWidget):
    def __init__(self,
                 camera_id: str,
                 camera_config: CameraConfig,
                 parent: QWidget = None):
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

        self._title_label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label_widget = QLabel("\U0001F4F8 Connecting... ")
        self._image_label_widget.setStyleSheet("border: 1px solid;")
        self._image_label_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._image_label_widget)

        self._luminance = []

    @property
    def camera_id(self):
        return self._camera_id

    @property
    def image_label_widget(self):
        return self._image_label_widget

    def calculate_mean_luminance(self, q_image: QImage):
        # Convert QImage to numpy array
        q_image_data = q_image.convertToFormat(QImage.Format.Format_RGB888)
        ptr = q_image_data.bits().asarray(q_image_data.sizeInBytes())
        image = np.frombuffer(ptr, np.uint8).reshape((q_image.height(), q_image.width(), 3))

        mean_luminance = np.mean(image)
        if mean_luminance > 200:
            f = 9
        return mean_luminance

    def handle_image_update(self, q_image: QImage, frame_info: dict):
        logger.trace(f"Handling image update for camera_id: {self._camera_id}")
        pixmap = QPixmap.fromImage(q_image)

        mean_luminance = self.calculate_mean_luminance(q_image)

        self._luminance.append(mean_luminance)
        logger.debug(
            f"Camera {self._camera_id} mean luminance on this frame: {mean_luminance}, average: {np.mean(self._luminance)}")

        image_label_widget_width = self._image_label_widget.width()
        image_label_widget_height = self._image_label_widget.height()

        scaled_width = int(image_label_widget_width * .95)
        scaled_height = int(image_label_widget_height * .95)

        pixmap = pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation, )

        self._image_label_widget.setPixmap(pixmap)

        queue_size = frame_info['queue_size']
        frames_recorded = frame_info['number_of_frames_recorded']

        if frames_recorded is None:
            frames_recorded = 0
        self._title_label_widget.setText(
            self._camera_name_string + f"\nQueue Size:{queue_size} | "
                                       f"Frames Recorded#{str(frames_recorded)}".ljust(38))

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
