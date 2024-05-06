import io
import time
from typing import Dict, Optional, List

import PIL.Image as Image
import msgpack
import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.detection.camera_id import CameraId
from skellycam.core.frames.multi_frame_payload import MultiFramePayload


class FrontendImagePayload(BaseModel):
    jpeg_images: Dict[CameraId, Optional[bytes]]
    utc_ns_to_perf_ns: Dict[str, int] = Field(
        description="A mapping of `time.time_ns()` to `time.perf_counter_ns()` "
                    "to allow conversion of `time.perf_counter_ns()`'s arbitrary "
                    "time base to unix time")
    prior_logs: List[str] = Field(default_factory=list,
                                  description="Lifecycle events for this payload from before it was converted "
                                              "to a FrontendImagePayload, format: f'{event_name}:{perf_counter_ns}'")
    logs: List[str] = Field(default_factory=list,
                            description="Lifecycle events for this payload after it was converted "
                                        "to a FrontendImagePayload, format: f'{event_name}:{perf_counter_ns}'")
    multi_frame_number: int = 0

    @property
    def camera_ids(self):
        self.log("check_camera_ids")
        return list(self.jpeg_images.keys())

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload, jpeg_quality: int = 90):

        instance = cls(utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns,
                       prior_logs=multi_frame_payload.logs,
                       multi_frame_number=multi_frame_payload.multi_frame_number,
                       logs=cls.init_logs(),
                       jpeg_images={})

        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is None:
                continue
            instance.log(f"before_converting_{camera_id}_to_jpeg_quality_{jpeg_quality}")
            instance[camera_id] = cls._image_to_jpeg(frame.image, jpeg_quality)
            instance.log(f"converted_{camera_id}_to_jpeg_quality_{jpeg_quality}")

        return instance

    def to_msgpack(self) -> bytes:
        self.log("to_msgpack")
        return msgpack.packb(self.dict(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        received_event = f"before_unpacking_msgpack:{time.perf_counter_ns()}"
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        instance = cls(**unpacked)
        instance.log(received_event, add_timestamp=False)
        instance.log("created_from_msgpack")
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

    def log(self, event_name: str, add_timestamp=True):
        if add_timestamp:
            self.logs.append(f"{event_name}:{time.perf_counter_ns()}")
        else:
            self.logs.append(event_name)

    @staticmethod
    def init_logs():
        return [f"created:{time.perf_counter_ns()}"]

    def __getitem__(self, key: CameraId):
        self.log(f"get_{key}")
        return self.jpeg_images[key]

    def __setitem__(self, key: CameraId, value: Optional[bytes]):
        self.log(f"set_{key}")
        self.jpeg_images[key] = value

    def __str__(self):
        self.log("cast_to_str")
        frame_strs = []
        for camera_id, frame in self.jpeg_images.items():
            if frame:
                frame_strs.append(f"{camera_id}: {len(frame)} bytes")
            else:
                frame_strs.append(f"{camera_id}: None")

        return ",".join(frame_strs)
