import base64
import time
from copy import deepcopy
from typing import Dict, Optional, List

import cv2
import msgpack
import numpy as np
from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFrameMetadata
from skellycam.core.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping


class FrontendFramePayload(BaseModel):
    jpeg_images: Dict[CameraId, Optional[str]]
    multi_frame_metadata: MultiFrameMetadata
    lifespan_timestamps_ns: List[Dict[str, int]]
    utc_ns_to_perf_ns: UtcToPerfCounterMapping
    multi_frame_number: int = 0

    @property
    def camera_ids(self):
        return list(self.jpeg_images.keys())

    def get_frame_by_camera_id(self, camera_id: CameraId) -> Optional[FramePayload]:
        if camera_id not in self.jpeg_images:
            return None
        jpeg_image = self.jpeg_images[camera_id]
        if jpeg_image is None:
            return None
        metadata = self.metadata[camera_id]
        return FramePayload.from_jpeg_image(jpeg_image=jpeg_image, metadata=metadata)

    @classmethod
    def from_multi_frame_payload(cls,
                                 multi_frame_payload: MultiFramePayload,
                                 resize_image: float,
                                 jpeg_quality: int = 90):

        if not multi_frame_payload.full:
            raise ValueError("MultiFramePayload must be full to convert to FrontendImagePayload")

        mf_metadata = multi_frame_payload.to_metadata()

        jpeg_images = {}
        for camera_id, frame in multi_frame_payload.frames.items():
            if frame is None:
                continue
            frame.metadata[FRAME_METADATA_MODEL.START_COMPRESS_TO_JPEG_TIMESTAMP_NS.value] = time.perf_counter_ns()
            jpeg_images[camera_id] = cls._image_to_jpeg(frame.image.copy(), quality=jpeg_quality, resize=resize_image)
            frame.metadata[FRAME_METADATA_MODEL.END_COMPRESS_TO_JPEG_TIMESTAMP_NS.value] = time.perf_counter_ns()
        lifespan_timestamps_ns = deepcopy(multi_frame_payload.lifespan_timestamps_ns)
        lifespan_timestamps_ns.append({"converted_to_frontend_payload": time.perf_counter_ns()})

        return cls(utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns,
                   multi_frame_number=multi_frame_payload.multi_frame_number,
                   lifespan_timestamps_ns=lifespan_timestamps_ns,
                   jpeg_images=jpeg_images,
                   multi_frame_metadata=mf_metadata)

    def to_msgpack(self) -> bytes:
        return msgpack.packb(self.model_dump(), use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        unpacked = msgpack.unpackb(msgpack_bytes, raw=False, use_list=False)
        instance = cls(**unpacked)
        return instance

    @staticmethod
    def _image_to_jpeg(image: np.ndarray, quality: int, resize: float) -> str:
        """
        Convert a numpy array image to a JPEG image using OpenCV.
        """
        if resize < 0 or resize > 1:
            raise ValueError("Resize must be between 0 and 1")
        # Encode the image as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        resized_image = cv2.resize(image, dsize=(int(image.shape[1] * resize), int(image.shape[0] * resize)))
        result, jpeg_image = cv2.imencode('.jpg', resized_image, encode_param)

        if not result:
            raise ValueError("Could not encode image to JPEG")
        base64_image = base64.b64encode(jpeg_image).decode('utf-8')
        return base64_image

    def __str__(self):
        total_bytes = sum([len(jpeg) for jpeg in self.jpeg_images.values()])
        out_str = f"FrontendImagePayload with {len(self.jpeg_images)} images: \n"
        frame_strs = []
        for camera_id, frame in self.jpeg_images.items():
            if frame:
                frame_strs.append(f"{camera_id}: {len(frame)} bytes, \n")
            else:
                frame_strs.append(f"{camera_id}: None")
        out_str += ",".join(frame_strs)
        out_str += f"Total size: {total_bytes} bytes\n"
        return out_str


def annotate_image(frame: FramePayload,
                   image: np.ndarray) -> np.ndarray:
    annotation_text = [
        f"Camera ID: {frame.camera_id}",
        f"Frames Read: {frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]}",
    ]
    font_scale = 1
    font_thickness = 2
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_outline_thickness = 2
    font_outline_color = (0, 0, 0)
    font_color = (255, 0, 255)
    font_position = (10, 40)  # Starting position (x, y)
    font_line_type = cv2.LINE_AA
    line_gap = 40  # Gap between lines

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
