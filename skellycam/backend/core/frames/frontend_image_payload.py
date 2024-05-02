from typing import Dict, Optional

import PIL.Image as Image
import io

import msgpack
import numpy as np
from pydantic import BaseModel

from skellycam.backend.core.device_detection.camera_id import CameraId
from skellycam.backend.core.frames.multi_frame_payload import MultiFramePayload


class FrontendImagePayload(BaseModel):
    jpeg_images: Dict[CameraId, Optional[bytes]]

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload):
        images = {camera_id: frame.image for camera_id, frame in multi_frame_payload.frames.items() if frame is not None}
        jpeg_images = {camera_id: cls._image_to_jpeg(image) for camera_id, image in images.items()}
        return cls(jpeg_images=jpeg_images)

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
