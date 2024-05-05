import io
from typing import Dict, Optional

import PIL.Image as Image
import cv2
import msgpack
import numpy as np
from pydantic import BaseModel

from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload


class FrontendImagePayload(BaseModel):
    jpeg_images_by_camera: Dict[CameraId, Optional[bytes]]

    @property
    def camera_ids(self):
        return list(self.jpeg_images_by_camera.keys())

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload, jpeg_quality: int = 90):
        jpeg_images = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is None:
                continue

            jpeg_images[camera_id] = cls._image_to_jpeg(frame.image, quality=jpeg_quality)
        return cls(jpeg_images_by_camera=jpeg_images)

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self.dict(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        return cls(**unpacked)

    @staticmethod
    def _image_to_jpeg(image: np.ndarray, quality: int = 95) -> bytes:
        """
        Convert a numpy array image to a JPEG image using PIL.
        """
        image = Image.fromarray(image)
        with io.BytesIO() as output:
            image.save(output, format="JPEG", quality=quality)
            return output.getvalue()

    def __len__(self):
        return len(self.jpeg_images_by_camera)
