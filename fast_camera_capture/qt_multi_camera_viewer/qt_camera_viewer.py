import cv2
import numpy as np
from PyQt6 import QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class CameraViewWorker:
    # this is a worker that handles incoming frames from a video stream
    def __init__(self, camera_id: str):
        self._q_label_widget = QLabel(f"Camera {camera_id}")

    @property
    def q_label_widget(self):
        return self._q_label_widget

    def update_image(self, image: np.ndarray):
        # update the image in the video label widget
        pixmap = self.convert_frame_to_pixmap(image)
        self._q_label_widget.setPixmap(pixmap)

    def convert_frame_to_pixmap(self, image: np.ndarray, scale: float = 1.0):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_width, image_height, image_color_channels = image.shape

        q_image = QtGui.QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QtGui.QImage.Format.Format_RGB888
        )

        pix = QtGui.QPixmap.fromImage(q_image)
        resized_pixmap = pix.scaled(
            int(image_width * scale),
            int(image_height * scale),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        return resized_pixmap

