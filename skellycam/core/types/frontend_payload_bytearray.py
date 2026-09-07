from dataclasses import dataclass

import logging

import cv2
import numpy as np
from numpy.typing import NDArray


logger = logging.getLogger(__name__)
from skellycam.core.types.type_overloads import FrameNumberInt, MultiframeTimestampFloat


class MessageType:
    PAYLOAD_HEADER = 0
    FRAME_HEADER = 1
    PAYLOAD_FOOTER = 2


FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE = np.dtype(
    [
        (
            "message_type",
            "<u1",
        ),  # 1 byte: 0 = payload_header, 1 = frame_header, 2 = payload_footer
        ("frame_number", "<i8"),  # 8 bytes, little-endian int64
        ("number_of_cameras", "<i4"),  # 4 bytes, little-endian int32
    ],
    align=True,
)

FRONTEND_FRAME_HEADER_DTYPE = np.dtype(
    [
        (
            "message_type",
            "<u1",
        ),  # 1 byte: 0 = payload_header, 1 = frame_header, 2 = payload_footer
        ("frame_number", "<i8"),  # 8 bytes, little-endian int64
        ("camera_id", "S16"),  # 16 bytes fixed-length camera ID
        ("camera_index", "<i4"),  # 4 bytes, little-endian int32
        ("image_width", "<i4"),  # 4 bytes, little-endian int32
        ("image_height", "<i4"),  # 4 bytes, little-endian int32
        ("color_channels", "<i4"),  # 4 bytes, little-endian int32
        (
            "jpeg_string_length",
            "<i4",
        ),  # 4 bytes, length of the JPEG string, little-endian int32
    ],
    align=True,
)

JPEG_ENCODING_PARAMETERS = [int(cv2.IMWRITE_JPEG_QUALITY), 60]


@dataclass(frozen=True)
class ImagePayloadFrame:
    """An oriented BGR image with explicit transport identity and output size.

    Transport IDs occupy the wire's ASCII camera slot. Playback sessions map
    these bounded IDs to full media identities separately from calibration IDs.
    The caller retains image ownership until encoding returns.
    """

    transport_id: str
    transport_index: int
    frame_number: int
    timestamp: float
    image: NDArray[np.uint8]
    output_width: int
    output_height: int

    def __post_init__(self) -> None:
        encoded_id = self.transport_id.encode("ascii")
        if not encoded_id or len(encoded_id) > 16 or b"\0" in encoded_id:
            raise ValueError("Image transport IDs must contain 1–16 non-null ASCII bytes")
        if self.frame_number < 0 or self.transport_index < 0:
            raise ValueError("Frame ordinal and transport index must be nonnegative")
        if not np.isfinite(self.timestamp):
            raise ValueError("Image timestamp must be finite")
        if self.image.dtype != np.uint8 or self.image.ndim != 3 or self.image.shape[2] != 3:
            raise ValueError("Image payload requires uint8 BGR pixels")
        if min(self.image.shape[:2]) < 1 or min(self.output_width, self.output_height) < 1:
            raise ValueError("Image dimensions must be positive")


@dataclass(frozen=True)
class ImagePayloadRequest:
    frames: tuple[ImagePayloadFrame, ...]
    jpeg_encoding_parameters: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("Cannot serialize an empty image group")
        if len({frame.frame_number for frame in self.frames}) != 1:
            raise ValueError("Camera frame numbers must agree")
        if len({frame.transport_id for frame in self.frames}) != len(self.frames):
            raise ValueError("Image transport IDs must be unique")
        if len({frame.transport_index for frame in self.frames}) != len(self.frames):
            raise ValueError("Image transport indices must be unique")
        if len(self.jpeg_encoding_parameters) % 2:
            raise ValueError("JPEG encoding parameters must be key/value pairs")


def encode_image_payload(request: ImagePayloadRequest) -> tuple[FrameNumberInt, MultiframeTimestampFloat, memoryview]:
    """Encode one synchronized image group into an independently owned wire buffer."""
    frame_number = request.frames[0].frame_number
    payload = bytearray()
    header = np.zeros(1, dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    header["message_type"] = MessageType.PAYLOAD_HEADER
    header["frame_number"] = frame_number
    header["number_of_cameras"] = len(request.frames)
    payload.extend(header.tobytes())
    for frame in request.frames:
        image = frame.image
        if image.shape[:2] != (frame.output_height, frame.output_width):
            image = cv2.resize(src=image, dsize=(frame.output_width, frame.output_height), interpolation=cv2.INTER_LINEAR)
        success, jpeg = cv2.imencode(ext=".jpg", img=image, params=list(request.jpeg_encoding_parameters))
        if not success:
            raise RuntimeError(f"JPEG encoding failed for image {frame.transport_id}")
        frame_header = np.zeros(1, dtype=FRONTEND_FRAME_HEADER_DTYPE)
        frame_header["message_type"] = MessageType.FRAME_HEADER
        frame_header["frame_number"] = frame_number
        frame_header["camera_id"] = frame.transport_id.encode("ascii")
        frame_header["camera_index"] = frame.transport_index
        frame_header["color_channels"] = 3
        frame_header["image_width"] = frame.output_width
        frame_header["image_height"] = frame.output_height
        frame_header["jpeg_string_length"] = jpeg.nbytes
        payload.extend(frame_header.tobytes())
        payload.extend(jpeg.tobytes())
    header["message_type"] = MessageType.PAYLOAD_FOOTER
    payload.extend(header.tobytes())
    return frame_number, float(np.mean([frame.timestamp for frame in request.frames])), memoryview(payload).toreadonly()


def create_frontend_payload(
    latest_frames: dict[str, np.recarray],
    display_image_sizes: dict[str, dict[str, float]] | None = None,
    jpeg_encoding_parameters: list[int] | None = None,
) -> tuple[FrameNumberInt, MultiframeTimestampFloat, memoryview]:
    """Adapt live camera records to the shared image encoder with live display policy."""
    frames: list[ImagePayloadFrame] = []
    for camera_id, record in latest_frames.items():
        rotation = int(record.frame_metadata.camera_info.rotation[0])
        image = cv2.rotate(src=record.image[0], rotateCode=rotation) if rotation != -1 else record.image[0]
        height, width = image.shape[:2]
        scale = 0.5
        if display_image_sizes is not None and camera_id in display_image_sizes:
            display = display_image_sizes[camera_id]
            scale = min(int(display["width"]) / width, int(display["height"]) / height, scale)
        frames.append(ImagePayloadFrame(
            transport_id=camera_id, transport_index=int(record.frame_metadata.camera_info.camera_index[0]),
            frame_number=int(record.frame_metadata.frame_number[0]),
            timestamp=float(np.mean([record.frame_metadata.timestamps.pre_frame_grab_ns,
                                     record.frame_metadata.timestamps.post_frame_grab_ns])),
            image=image, output_width=int(width * scale), output_height=int(height * scale),
        ))
    return encode_image_payload(ImagePayloadRequest(frames=tuple(frames),
        jpeg_encoding_parameters=tuple(JPEG_ENCODING_PARAMETERS if jpeg_encoding_parameters is None else jpeg_encoding_parameters)))
