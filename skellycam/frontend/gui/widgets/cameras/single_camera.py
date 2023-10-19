import pprint
from typing import Any, Dict

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frames.frontend import FrontendFramePayload


class SingleCameraView(QWidget):
    def __init__(self,
                 camera_config: CameraConfig,
                 parent: QWidget = None):
        super().__init__(parent=parent)

        self._camera_id = camera_config.camera_id
        self._annotation_text = pprint.pformat(camera_config.dict())
        self._pixmap = QPixmap()
        self._painter = QPainter()
        self._initUI()

    def _initUI(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._camera_name_string = f"Camera {self._camera_id}"
        self._title_label = QLabel(self._camera_name_string, parent=self)
        self._layout.addWidget(self._title_label)
        self._title_label.setStyleSheet("""
                           font-size: 12px;
                           font-weight: bold;
                           font-family: "Dosis", sans-serif;
                           color: #000000;
                           """)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_view = QLabel(f"\U0001F4F8 Connecting... \n\n {self._annotation_text}", parent=self)
        self._image_view.setStyleSheet("border: 1px solid;")
        self._image_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._image_view)

    def handle_image_update(self, frame: FrontendFramePayload):
        self._pixmap.convertFromImage(frame.q_image)

        image_label_widget_width = self._image_view.width()
        image_label_widget_height = self._image_view.height()

        scaled_width = int(image_label_widget_width * .95)
        scaled_height = int(image_label_widget_height * .95)

        self._pixmap = self._pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation, )

        self._image_view.setPixmap(self._pixmap)
        #
        # q_size = frame_diagnostics_dictionary['queue_size']
        # frames_recorded = frame_diagnostics_dictionary['frames_recorded']
        # if frames_recorded is None:
        #     frames_recorded = 0
        # self._title_label.setText(
        #     self._camera_name_string + f"\nQueue Size:{q_size} | "
        #                                f"Frames Recorded#{str(frames_recorded)}".ljust(38))

    def show(self):
        super().show()
        self._image_view.show()
        self._title_label.show()

    def hide(self):
        super().hide()
        self._image_view.hide()
        self._title_label.hide()

    def close(self):
        self._image_view.close()
        self._title_label.close()
        super().close()

    def paintEvent(self, event):
        super().paintEvent(event)

        self._painter.begin(self._image_view.pixmap())
        self._painter.setPen(QColor(255, 0, 0))  # Red color
        self._painter.drawText(event.rect(), Qt.AlignCenter, self._annotation_text)
        self._painter.end()

