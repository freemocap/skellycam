import logging

import cv2
import numpy as np


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


def create_frontend_payload(
    latest_frames: dict[str, np.recarray],
    display_image_sizes: dict[str, dict[str, float]] | None = None,
    jpeg_encoding_parameters: list[int] | None = None,
) -> tuple[FrameNumberInt, MultiframeTimestampFloat, memoryview]:
    """
    Convert a multi-frame record array into bytes for websocket transmission.

    Args:
        latest_frames: Dictionary of camera_id to frame recarray
        display_image_sizes: Optional display sizes for each camera
        jpeg_encoding_parameters: JPEG encoding parameters

    Returns:
        Tuple of (frame_number, mean_timestamp, payload_view)

    Each returned read-only view owns a distinct backing buffer. Building another
    payload cannot mutate it, including while an asynchronous send is suspended.
    No view is exported until all buffer growth is complete.
    """
    payload = bytearray()

    if jpeg_encoding_parameters is None:
        jpeg_encoding_parameters = JPEG_ENCODING_PARAMETERS

    if not latest_frames:
        raise ValueError("Cannot serialize an empty camera group")
    camera_ids = list(latest_frames.keys())
    frame_numbers = [
        latest_frames[camera_id].frame_metadata.frame_number[0]
        for camera_id in camera_ids
    ]

    if len(set(frame_numbers)) != 1:
        raise ValueError(f"Camera frame numbers must agree: {frame_numbers}")

    frame_number = frame_numbers[0]
    number_of_cameras = len(camera_ids)

    current_pos = 0

    # Add header with proper message type
    payload_header = np.recarray(1, dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    payload_header.message_type = MessageType.PAYLOAD_HEADER
    payload_header.frame_number = frame_number
    payload_header.number_of_cameras = number_of_cameras
    header_bytes = payload_header.tobytes()
    payload[current_pos : current_pos + len(header_bytes)] = header_bytes
    current_pos += len(header_bytes)

    image_scale = 0.5
    frame_timestamps: list[float | np.floating] = []

    for camera_id in camera_ids:
        frame_recarray = latest_frames[camera_id]
        frame_timestamps.append(
            np.mean(
                [
                    frame_recarray.frame_metadata.timestamps.pre_frame_grab_ns,
                    frame_recarray.frame_metadata.timestamps.post_frame_grab_ns,
                ]
            )
        )

        # Handle image rotation
        if frame_recarray.frame_metadata.camera_info.rotation != -1:
            rotated_image = cv2.rotate(
                src=frame_recarray.image[0],
                rotateCode=frame_recarray.frame_metadata.camera_info.rotation[0],
            )
        else:
            rotated_image = frame_recarray.image[0]

        orig_h, orig_w = rotated_image.shape[:2]

        if display_image_sizes is None or camera_id not in display_image_sizes:
            resize_image_width = int(orig_w * image_scale)
            resize_image_height = int(orig_h * image_scale)
        else:
            display_w = int(display_image_sizes[camera_id]["width"])
            display_h = int(display_image_sizes[camera_id]["height"])
            # Fit the image within the display box while PRESERVING aspect ratio.
            # A uniform scale factor avoids the independent-axis clamping that
            # would squish/stretch the image when the display aspect ratio
            # differs from the camera's native aspect ratio.
            scale = min(
                display_w / orig_w,
                display_h / orig_h,
                image_scale,
            )
            resize_image_width = int(orig_w * scale)
            resize_image_height = int(orig_h * scale)

        # Resize and encode image
        resized_img = cv2.resize(
            src=rotated_image,
            dsize=(resize_image_width, resize_image_height),
            interpolation=cv2.INTER_LINEAR,
        )
        encoded, jpeg_data = cv2.imencode(
            ext=".jpg", img=resized_img, params=jpeg_encoding_parameters
        )
        if not encoded:
            raise RuntimeError(f"JPEG encoding failed for camera {camera_id}")
        jpeg_string = jpeg_data.tobytes()
        jpeg_string_length = len(jpeg_string)

        # Create frame header
        frame_header = np.recarray(1, dtype=FRONTEND_FRAME_HEADER_DTYPE)
        frame_header.message_type = MessageType.FRAME_HEADER
        frame_header.frame_number = frame_number
        frame_header.camera_id = camera_id.encode("utf-8")[:16]  # Truncate if necessary
        frame_header.camera_index = (
            frame_recarray.frame_metadata.camera_info.camera_index[0]
        )
        frame_header.color_channels = (
            frame_recarray.frame_metadata.camera_info.color_channels[0]
        )
        frame_header.image_width = resize_image_width
        frame_header.image_height = resize_image_height
        frame_header.jpeg_string_length = jpeg_string_length

        frame_header_bytes = frame_header.tobytes()

        # Copy data
        payload[current_pos : current_pos + len(frame_header_bytes)] = (
            frame_header_bytes
        )
        current_pos += len(frame_header_bytes)
        payload[current_pos : current_pos + jpeg_string_length] = jpeg_string
        current_pos += jpeg_string_length

    # Add footer with proper message type
    payload_footer = np.array(
        [(MessageType.PAYLOAD_FOOTER, frame_number, number_of_cameras)],
        dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE,
    )
    footer_bytes = payload_footer.tobytes()

    payload[current_pos : current_pos + len(footer_bytes)] = footer_bytes
    current_pos += len(footer_bytes)

    frontend_bytes = memoryview(payload).toreadonly()

    return frame_number, np.mean(frame_timestamps), frontend_bytes
