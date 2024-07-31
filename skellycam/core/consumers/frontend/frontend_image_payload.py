from typing import Dict, Optional

import cv2
import msgpack
import numpy as np
from pydantic import BaseModel, Field

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.frames.multi_frame_payload import MultiFramePayload


class FrontendImagePayload(BaseModel):
    jpeg_images: Dict[CameraId, Optional[bytes]]
    utc_ns_to_perf_ns: Dict[str, int] = Field(
        description="A mapping of `time.time_ns()` to `time.perf_counter_ns()` "
                    "to allow conversion of `time.perf_counter_ns()`'s arbitrary "
                    "time base to unix time")
    multi_frame_number: int = 0

    @property
    def camera_ids(self):
        return list(self.jpeg_images.keys())

    @classmethod
    def from_multi_frame_payload(cls,
                                 multi_frame_payload: MultiFramePayload,
                                 jpeg_quality: int = 90):
        if not multi_frame_payload.full:
            raise ValueError("MultiFramePayload must be full to convert to FrontendImagePayload")

        jpeg_images = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is None:
                continue
            frontend_image = frame.image.copy()
            # frontend_image = cv2.resize(frontend_image, (0, 0), fx=0.5, fy=0.5)
            jpeg_images[camera_id] = cls._image_to_jpeg(frontend_image, quality=jpeg_quality)

        return cls(utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns,
                   multi_frame_number=multi_frame_payload.multi_frame_number,
                   jpeg_images=jpeg_images)

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self.model_dump(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        instance = cls(**unpacked)
        return instance

    @staticmethod
    def _image_to_jpeg(image: np.ndarray, quality: int = 95) -> bytes:
        """
        Convert a numpy array image to a JPEG image using OpenCV.
        """
        # Encode the image as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        result, jpeg_image = cv2.imencode('.jpg', image, encode_param)

        if not result:
            raise ValueError("Could not encode image to JPEG")

        return jpeg_image.tobytes()

    @staticmethod
    def _annotate_image(frame: FramePayload,
                        image=np.ndarray) -> np.ndarray:
        annotation_text = [
            f"Camera ID: {frame.camera_id}",
            f"Frame Number: {frame.frame_number}",
        ]
        font_scale = 0.5
        font_thickness = 1
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_outline_thickness = 2
        font_outline_color = (0, 0, 0)
        font_color = (255, 0, 255)
        font_position = (10, 20)  # Starting position (x, y)
        font_line_type = cv2.LINE_AA
        line_gap = 20  # Gap between lines

        for i, line in enumerate(annotation_text):
            y_pos = font_position[1] + i * line_gap
            # draw text outline
            image = cv2.putText(image,
                                line,
                                (font_position[0], y_pos),
                                font,
                                font_scale,
                                font_outline_color,
                                font_outline_thickness,
                                font_line_type)
            # draw text
            image = cv2.putText(image,
                                line,
                                (font_position[0], y_pos),
                                font,
                                font_scale,
                                font_color,
                                font_thickness,
                                font_line_type)

        return image

    def __str__(self):
        frame_strs = []
        for camera_id, frame in self.jpeg_images.items():
            if frame:
                frame_strs.append(f"{camera_id}: {len(frame)} bytes")
            else:
                frame_strs.append(f"{camera_id}: None")

        return ",".join(frame_strs)
