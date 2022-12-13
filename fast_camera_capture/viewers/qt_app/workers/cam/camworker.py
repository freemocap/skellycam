import time
from typing import List

import cv2
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage

from fast_camera_capture.detection.models.frame_payload import FramePayload
from fast_camera_capture.opencv.camera.types.camera_id import CameraId
from fast_camera_capture.opencv.group.camera_group import CameraGroup


class CamGroupFrameWorker(QThread):
    ImageUpdate = pyqtSignal(CameraId, QImage)

    def __init__(self, cam_ids: List[str], parent=None):
        super().__init__(parent=parent)
        self._cam_ids = cam_ids
        self._cam_group = CameraGroup(cam_ids)

    def run(self):
        self._cam_group.start()
        while self._cam_group.is_capturing:
            frame_obj = self._cam_group.latest_frames()
            for camera_id, frame in frame_obj.items():
                if frame:
                    qimage = self._convert_frame(frame)
                    self.ImageUpdate.emit(camera_id, qimage)


    def _convert_frame(self, frame: FramePayload):
        image = frame.image
        # image = cv2.flip(image, 1)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        converted_frame = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QImage.Format.Format_RGB888,
        )
        return converted_frame.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)

    def close(self):
        self._cam_group.close()
