import io
from typing import Dict, Optional

import PIL.Image as Image
import cv2
import msgpack
import numpy as np
from pydantic import BaseModel

from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.frame_payload import FramePayload
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload


class FrontendImagePayload(BaseModel):
    jpeg_images_by_camera: Dict[CameraId, Optional[bytes]]

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload, resize: Optional[float] = 1):
        jpeg_images = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is None:
                continue

            if resize is not None and resize != 1.0:
                resized_image = cv2.resize(frame.image, (0, 0), fx=resize, fy=resize)
            else:
                resized_image = frame.image
            jpeg_images[camera_id] = cls._image_to_jpeg(resized_image)
        return cls(jpeg_images_by_camera=jpeg_images)

    @classmethod
    def from_frame_payload(cls, frame: FramePayload, resize: Optional[float] = 1):
        if resize is not None and resize != 1.0:
            resized_image = cv2.resize(frame.image, (0, 0), fx=resize, fy=resize)
        else:
            resized_image = frame.image
        jpeg_images = {frame.camera_id: cls._image_to_jpeg(resized_image)}
        return cls(jpeg_images_by_camera=jpeg_images)

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self.dict(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        return cls(**unpacked)

    @staticmethod
    def _image_to_jpeg(image: np.ndarray) -> bytes:
        """
        Convert a numpy array image to a JPEG image using PIL.
        """
        image = Image.fromarray(image)
        with io.BytesIO() as output:
            image.save(output, format='JPEG')
            return output.getvalue()
