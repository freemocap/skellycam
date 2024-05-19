import io
from typing import Dict, Optional

import PIL.Image as Image
import msgpack
import numpy as np
from pydantic import BaseModel, Field

from skellycam.core import CameraId
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
            jpeg_images[camera_id] = cls._image_to_jpeg(frame.image, jpeg_quality)

        return cls(utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns,
                   multi_frame_number=multi_frame_payload.multi_frame_number,
                   jpeg_images=jpeg_images)

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self.dict(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        instance = cls(**unpacked)
        return instance

    @staticmethod
    def _image_to_jpeg(image: np.ndarray, quality: int = 95) -> bytes:
        """
        Convert a numpy array image to a JPEG image using PIL.
        """
        image = Image.fromarray(image)
        with io.BytesIO() as output:
            image.save(output, format="JPEG", quality=quality)
            return output.getvalue()

    def __str__(self):
        frame_strs = []
        for camera_id, frame in self.jpeg_images.items():
            if frame:
                frame_strs.append(f"{camera_id}: {len(frame)} bytes")
            else:
                frame_strs.append(f"{camera_id}: None")

        return ",".join(frame_strs)
