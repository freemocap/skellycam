import base64
import time
from io import BytesIO
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel

from skellycam.core import CameraIndex
from skellycam.core.camera_group.camera.config.camera_config import CameraConfig, CameraConfigs, CameraIdString
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload, MultiFrameMetadata
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping

Base64JPEGImage = str  # Base64 encoded JPEG image
class FrontendFramePayload(BaseModel):
    jpeg_images: dict[CameraIdString, Base64JPEGImage]
    camera_configs: CameraConfigs
    multi_frame_metadata: MultiFrameMetadata
    utc_ns_to_perf_ns: UtcToPerfCounterMapping
    multi_frame_number: int = 0
    backend_framerate: CurrentFramerate | None = None
    frontend_framerate: CurrentFramerate | None = None

    @property
    def camera_ids(self):
        return list(self.jpeg_images.keys())


    @classmethod
    def from_multi_frame_payload(cls,
                                 multi_frame_payload: MultiFramePayload,
                                 image_sizes: dict[CameraIndex, dict[str, int]]|None = None,
                                 resize_image: float = .5,
                                 jpeg_quality: int = 80):

        if not multi_frame_payload.full:
            raise ValueError("MultiFramePayload must be full to convert to FrontendImagePayload")

        mf_metadata = multi_frame_payload.to_metadata()

        jpeg_images = {}
        for camera_id in multi_frame_payload.frames.keys():
            frame = multi_frame_payload.get_frame(camera_id)
            frame.metadata[FRAME_METADATA_MODEL.START_COMPRESS_TO_JPEG_TIMESTAMP_NS.value] = time.perf_counter_ns()
            resized_image = cls._resize_image(frame=frame,
                                              image_sizes=image_sizes,
                                              fallback_resize_ratio=resize_image)
            jpeg_images[camera_id] = cls._image_to_jpeg_cv2(resized_image, quality=jpeg_quality)
            frame.metadata[FRAME_METADATA_MODEL.END_COMPRESS_TO_JPEG_TIMESTAMP_NS.value] = time.perf_counter_ns()

        return cls(utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns,
                   multi_frame_number=multi_frame_payload.multi_frame_number,
                   jpeg_images=jpeg_images,
                   multi_frame_metadata=mf_metadata,
                   camera_configs=multi_frame_payload.camera_configs,
                   backend_framerate=multi_frame_payload.backend_framerate,
                   frontend_framerate=multi_frame_payload.frontend_framerate)

    @staticmethod
    def _resize_image(frame: FramePayload,
                      image_sizes: Dict[CameraIndex, Dict[str, int]],
                      fallback_resize_ratio: float) -> np.ndarray:
        # TODO - Pydantic model for images sizes (NOT the same as the frontend CameraViewSizes, to avoid circular imports)
        image = frame.image
        camera_id = frame.camera_id
        if image_sizes is None or str(camera_id) not in image_sizes.keys():
            og_height, og_width, _ = image.shape
            new_width = int(og_width * fallback_resize_ratio)
            new_height = int(og_height * fallback_resize_ratio)
        else:
            new_width = image_sizes[camera_id]["width"]
            new_height = image_sizes[camera_id]["height"]

        return cv2.resize(image, dsize=(new_width, new_height))

    @staticmethod
    def _image_to_jpeg_cv2(image: np.ndarray, quality: int) -> str:
        """
        Convert a numpy array image to a JPEG image using OpenCV.

        NOTE - Diagnostics in `/skellycam/skellycam/system/diagnostics/jpeg_compression_duration_by_settings.py` suggest that PIL is way faster than CV2 for this operation, but in practice it didn't seem so?
        """

        # Encode the image as JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

        result, jpeg_image = cv2.imencode('.jpg', image, encode_param)

        if not result:
            raise ValueError("Could not encode image to JPEG")
        base64_image = base64.b64encode(jpeg_image).decode('utf-8')
        return base64_image

    @staticmethod
    def _image_to_jpeg_pil(image: np.ndarray, quality: int, resize: float) -> str:
        """
        Convert a numpy array image to a JPEG image using PIL.
        """
        if resize < 0 or resize > 1:
            raise ValueError("Resize must be between 0 and 1")

        # Convert numpy array to PIL image
        pil_image = Image.fromarray(image)

        # Resize the image
        new_size = (int(pil_image.width * resize), int(pil_image.height * resize))
        resized_image = pil_image.resize(new_size)

        # Encode the image as JPEG
        buffer = BytesIO()
        resized_image.save(buffer, format='JPEG', quality=quality)
        jpeg_image = buffer.getvalue()

        # Convert to base64
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
