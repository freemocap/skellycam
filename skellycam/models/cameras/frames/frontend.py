from typing import Dict, Any, List

import cv2
from PySide6.QtGui import QImage
from pydantic import BaseModel

from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class FrontendFramePayload(BaseModel):
    camera_id: str
    q_image: QImage
    diagnostics: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_frame_payload(cls, frame: FramePayload):
        """
        Convert np.ndarray to QImage
        """

        frame.image = cv2.resize(frame.image, (0, 0), fx=0.5, fy=0.5)

        q_image = QImage(frame.image.data.tobytes(),
                         frame.image.shape[1],
                         frame.image.shape[0],
                         frame.image.strides[0],
                         QImage.Format_RGB888)

        return cls(camera_id=frame.camera_id,
                   q_image=q_image,
                   diagnostics={"frame_number": frame.number_of_frames_received})


class FrontendMultiFramePayload(BaseModel):
    frames: Dict[str, FrontendFramePayload]

    @property
    def full(self):
        return not any([frame is None for frame in self.frames.values()])

    @classmethod
    def from_camera_ids(cls, camera_ids: List[CameraId]):
        return cls(frames={camera_id: None for camera_id in camera_ids})

    def add_frame(self, frame: FramePayload):
        self.frames[frame.camera_id] = FrontendFramePayload.from_frame_payload(frame=frame)
