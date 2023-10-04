import skellycam
import logging
import sys
import time
from pathlib import Path

import cv2
from PySide6.QtCore import QUrl, QObject, Signal, QTimer
from PySide6.QtGui import QImage
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QVBoxLayout, QWidget, QApplication

logger = logging.getLogger(__name__)


class QMLCamera(QWidget):
    def __init__(self):
        logger.debug("Initializing QMLCamera")
        super().__init__()

        # QQuickWidget for embedding QML
        camera_view_qml_path = str(Path(__file__).parent / "single_camera.qml")
        logger.debug(f"Setting up QML widget with QML file: {camera_view_qml_path}")
        self.qml_widget = QQuickWidget()
        self.qml_widget.setSource(QUrl.fromLocalFile(camera_view_qml_path))
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.qml_widget.statusChanged.connect(self.on_status_changed)

        self.root_object = None
        self.qml_image = None

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.qml_widget)

    def on_status_changed(self, status):
        if status == QQuickWidget.Ready:
            self.root_object = self.qml_widget.rootObject()


#

class TestWebcamCapture(QObject):
    new_frame_signal = Signal(QImage)

    def __init__(self):
        logger.debug("Initializing TestWebcamCapture")
        super().__init__()

        self.capture = cv2.VideoCapture(0)
        self.exit = False

    def start_capture(self):
        while not self.exit:
            time.sleep(.01)
            logger.debug("Capturing frame")
            ret, frame = self.capture.read()
            if ret:
                logger.debug("Frame captured with size: " + str(frame.shape))
                q_image = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_RGB888).rgbSwapped()
                self.new_frame_signal.emit(q_image)


if __name__ == "__main__":
    logger.info(f"Running {__file__} as main script.")
    app = QApplication(sys.argv)

    qml_camera_widget = QMLCamera()
    time.sleep(2)
    webcam_capture = TestWebcamCapture()
    webcam_capture.new_frame_signal.connect(qml_camera_widget.root_object.updateImage)
    webcam_capture.start_capture()
    qml_camera_widget.show()

    sys.exit(app.exec())
