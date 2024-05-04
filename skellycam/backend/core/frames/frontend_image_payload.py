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
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload, resize_long_axis: Optional[int] = 640):
        jpeg_images = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is None:
                continue

            if resize_long_axis is not None:
                long_axis = max(frame.image.shape[:2])
                resize_proportion = resize_long_axis / long_axis
                resized_image = cv2.resize(frame.image, (0, 0), fx=resize_proportion, fy=resize_proportion)
            else:
                resized_image = frame.image
            jpeg_images[camera_id] = cls._image_to_jpeg(resized_image)
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

    def __len__(self):
        return len(self.jpeg_images_by_camera)