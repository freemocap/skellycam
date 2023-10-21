import pprint

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frames.frame_payload import FramePayload


class SingleCameraView(QWidget):
    def __init__(self,
                 camera_config: CameraConfig,
                 parent: QWidget = None):
        super().__init__(parent=parent)

        self._camera_id = camera_config.camera_id
        self._annotation_text = pprint.pformat(camera_config.dict())
        self._pixmap = QPixmap()
        self._painter = QPainter()
        self._processing_frame = False
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

    def handle_image_update(self, frame: FramePayload):
        if self._processing_frame:
            return  # Don't process frames faster than we can display them
        else:
            self._processing_frame = True

        q_image = frame.to_q_image()
        pixmap = QPixmap.fromImage(q_image)

        image_label_widget_width = self._image_view.width()
        image_label_widget_height = self._image_view.height()

        scaled_width = int(image_label_widget_width * .95)
        scaled_height = int(image_label_widget_height * .95)

        pixmap = pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation, )

        self._image_view.setPixmap(pixmap)
        self._processing_frame = False

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


