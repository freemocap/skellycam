import logging
import time

import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from skellycam import CameraConfig
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.image_annotator import ImageAnnotator

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
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._camera_name_string = f"Camera {self._camera_id}"

        # self._title_label_widget = QLabel(self._camera_name_string, parent=self)
        # self._layout.addWidget(self._title_label_widget)
        # self._title_label_widget.setStyleSheet("""
        #                    font-size: 12px;
        #                    font-weight: bold;
        #                    font-family: "Dosis", sans-serif;
        #                    color: #000000;
        #                    """)
        #
        # self._title_label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label_widget = QLabel("\U0001F4F8 Connecting... ")
        self._layout.addWidget(self._image_label_widget)
        self._image_label_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @property
    def camera_id(self):
        return self._camera_id



    def handle_image_update(self, frame_payload: FramePayload):
        if frame_payload.image is None:
            image = np.zeros((480, 640, 3), np.uint8)
            image[:] = (100, 100, 100)
            cv2.putText(image, "No Image Recieved", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 4)
        else:
            image = frame_payload.image

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = ImageAnnotator().annotate(image=image,
                                          text=self._camera_name_string,
                                          x=50,
                                          y=100,
                                          scale=2,
                                          line_thickness=8,
                                          color=(0, 0, 0))
        image = ImageAnnotator().annotate(image=image,
                                          text=f"Frames received : {frame_payload.number_of_frames_received}",
                                          x=50,
                                          y=130,
                                          scale=1,
                                          line_thickness=8,
                                          color=(0, 0, 0))
        image = ImageAnnotator().annotate(image=image,
                                          text=f"Frames recorded: {frame_payload.number_of_frames_recorded}",
                                          x=50,
                                          y=160,
                                          scale=1,
                                          line_thickness=8,
                                          color=(0, 0, 0))
        image = ImageAnnotator().annotate(image=image,
                                          text=f"Current chunk size: {frame_payload.current_chunk_size}",
                                          x=50,
                                          y=190,
                                          scale=1,
                                          line_thickness=8,
                                          color=(0, 0, 0))

        q_image = self._convert_to_q_image(image)
        pixmap = QPixmap.fromImage(q_image)

        image_label_widget_width = self._image_label_widget.width()
        image_label_widget_height = self._image_label_widget.height()

        scaled_width = int(image_label_widget_width * .99)
        scaled_height = int(image_label_widget_height * .99)

        pixmap = pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation, )

        self._image_label_widget.setPixmap(pixmap)

    def _convert_to_q_image(self, image: np.ndarray):
        # image = cv2.flip(image, 1)
        converted_frame = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QImage.Format.Format_RGB888,
        )

        return converted_frame.scaled(int(image.shape[1] / 2), int(image.shape[0] / 2),
                                      Qt.AspectRatioMode.KeepAspectRatio)

    def show(self):
        super().show()
        self._image_label_widget.show()
        # self._title_label_widget.show()

    def hide(self):
        super().hide()
        self._image_label_widget.hide()
        # self._title_label_widget.hide()

    def close(self):
        self._image_label_widget.close()
        # self._title_label_widget.close()
        super().close()
