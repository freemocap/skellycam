import logging
import threading
import time
from collections import defaultdict

import cv2
import numpy as np

from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import ONE_MEGABYTE, ONE_KILOBYTE
from skellycam.core.types.type_overloads import CameraGroupIdString, FrameNumberInt, MultiframeTimestampFloat

logger = logging.getLogger(__name__)

# Pipeline timing row keys (merged into websocket ``per_camera`` for UI).
PREVIEW_TIMING_JPEG_ROTATE_MS = "jpeg_rotate_ms"
PREVIEW_TIMING_JPEG_RESIZE_MS = "jpeg_resize_ms"
PREVIEW_TIMING_JPEG_ENCODE_MS = "jpeg_encode_ms"
# Wall-clock for entire multiplex binary (header + all cameras + footer) in create_frontend_payload.
PREVIEW_TIMING_WS_PAYLOAD_PREPARE_MS = "ws_payload_prepare_ms"
# Per multiframe: max(post_frame_grab_ns) - min(...) across cameras, in ms (live preview telemetry).
PREVIEW_MULTIFRAME_INTER_CAMERA_GRAB_SPREAD_MS = "inter_camera_grab_spread_ms"

# Thread-safe rolling samples for telemetry (drained by websocket relay).
_frontend_preview_timing_lock = threading.Lock()
_frontend_preview_timing_samples: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
    lambda: defaultdict(lambda: defaultdict(list))
)
_MAX_FRONTEND_PREVIEW_TIMING_SAMPLES_PER_STAGE = 512

_frontend_preview_multiframe_lock = threading.Lock()
_frontend_preview_multiframe_samples: dict[str, dict[str, list[float]]] = defaultdict(
    lambda: defaultdict(list)
)
_MAX_FRONTEND_PREVIEW_MULTIFRAME_SAMPLES_PER_STAGE = 512


def record_frontend_preview_multiframe_ms(
    camera_group_id: str, stage: str, elapsed_ms: float
) -> None:
    """Append one multiframe-wide preview telemetry sample (ms) for a logical stage."""
    with _frontend_preview_multiframe_lock:
        bucket = _frontend_preview_multiframe_samples[camera_group_id][stage]
        bucket.append(elapsed_ms)
        if len(bucket) > _MAX_FRONTEND_PREVIEW_MULTIFRAME_SAMPLES_PER_STAGE:
            del bucket[: len(bucket) - _MAX_FRONTEND_PREVIEW_MULTIFRAME_SAMPLES_PER_STAGE]


def get_and_clear_frontend_preview_multiframe_samples(
    camera_group_id: str,
) -> dict[str, list[float]]:
    """Pop all pending multiframe preview samples: ``stage -> list of ms``."""
    with _frontend_preview_multiframe_lock:
        raw = _frontend_preview_multiframe_samples.pop(camera_group_id, {})
        return {stage: list(samples) for stage, samples in raw.items()}


def record_frontend_preview_timing_ms(
    camera_group_id: str, camera_id: str, stage: str, elapsed_ms: float
) -> None:
    """Append one server-side preview step duration (ms) for telemetry."""
    with _frontend_preview_timing_lock:
        bucket = _frontend_preview_timing_samples[camera_group_id][camera_id][stage]
        bucket.append(elapsed_ms)
        if len(bucket) > _MAX_FRONTEND_PREVIEW_TIMING_SAMPLES_PER_STAGE:
            del bucket[: len(bucket) - _MAX_FRONTEND_PREVIEW_TIMING_SAMPLES_PER_STAGE]


def get_and_clear_frontend_preview_timing_samples(
    camera_group_id: str,
) -> dict[str, dict[str, list[float]]]:
    """Pop all pending preview timing samples: ``camera_id -> stage -> list of ms``."""
    with _frontend_preview_timing_lock:
        raw = _frontend_preview_timing_samples.pop(camera_group_id, {})
        return {
            str(cam_id): {stage: list(samples) for stage, samples in stages.items()}
            for cam_id, stages in raw.items()
        }


def record_jpeg_encode_ms(camera_group_id: str, camera_id: str, elapsed_ms: float) -> None:
    """Record JPEG encode duration only (alias for external callers/tests)."""
    record_frontend_preview_timing_ms(
        camera_group_id, camera_id, PREVIEW_TIMING_JPEG_ENCODE_MS, elapsed_ms
    )


class MessageType:
    PAYLOAD_HEADER = 0
    FRAME_HEADER = 1
    PAYLOAD_FOOTER = 2

FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE = np.dtype([
    ('message_type', '<u1'),  # 1 byte: 0 = payload_header, 1 = frame_header, 2 = payload_footer
    ('frame_number', '<i8'),  # 8 bytes, little-endian int64
    ('number_of_cameras', '<i4'),  # 4 bytes, little-endian int32
], align=True)

FRONTEND_FRAME_HEADER_DTYPE = np.dtype([
    ('message_type', '<u1'),  # 1 byte: 0 = payload_header, 1 = frame_header, 2 = payload_footer
    ('frame_number', '<i8'),  # 8 bytes, little-endian int64
    ('camera_id', 'S16'),  # 16 bytes fixed-length camera ID
    ('camera_index', '<i4'),  # 4 bytes, little-endian int32
    ('image_width', '<i4'),  # 4 bytes, little-endian int32
    ('image_height', '<i4'),  # 4 bytes, little-endian int32
    ('color_channels', '<i4'),  # 4 bytes, little-endian int32
    ('jpeg_string_length', '<i4'),  # 4 bytes, length of the JPEG string, little-endian int32
], align=True)

JPEG_ENCODING_PARAMETERS = [int(cv2.IMWRITE_JPEG_QUALITY), 80]


_reusable_bytes_payload: bytearray = bytearray(0)


def create_frontend_payload(
        latest_frames: dict[str, np.recarray],
        display_image_sizes: dict[str, dict[str, float]] | None = None,
        jpeg_encoding_parameters: list[int] | None = None,
        camera_group_id: CameraGroupIdString | None = None,
) -> tuple[FrameNumberInt, MultiframeTimestampFloat, bytearray]:
    """
    Convert a multi-frame record array into bytes for websocket transmission.

    Args:
        latest_frames: Dictionary of camera_id to frame recarray
        display_image_sizes: Optional display sizes for each camera
        jpeg_encoding_parameters: JPEG encoding parameters

    Returns:
        Tuple of (frame_number, mean_timestamp, payload_bytes)
    """
    global _reusable_bytes_payload

    if jpeg_encoding_parameters is None:
        jpeg_encoding_parameters = JPEG_ENCODING_PARAMETERS

    camera_ids = list(latest_frames.keys())
    frame_numbers = [latest_frames[camera_id].frame_metadata.frame_number[0] for camera_id in camera_ids]

    if len(set(frame_numbers)) != 1:
        logger.warning(f"All cameras in the multi-frame record array must have the same frame number: {frame_numbers}")

    frame_number = frame_numbers[0]
    number_of_cameras = len(camera_ids)

    cg_id = str(camera_group_id) if camera_group_id is not None else None
    if cg_id is not None and camera_ids:
        posts = [
            int(latest_frames[camera_id].frame_metadata.timestamps.post_frame_grab_ns[0])
            for camera_id in camera_ids
        ]
        spread_ms = (max(posts) - min(posts)) / 1e6
        record_frontend_preview_multiframe_ms(
            cg_id, PREVIEW_MULTIFRAME_INTER_CAMERA_GRAB_SPREAD_MS, spread_ms
        )

    t_ws_payload_prepare0 = time.perf_counter()

    # Pre-allocate with extra space for config data
    config_overhead = 300 * number_of_cameras  # Full config is included
    estimated_size = (number_of_cameras + 1) * ONE_MEGABYTE + config_overhead

    if len(_reusable_bytes_payload) < estimated_size:
        if len(_reusable_bytes_payload) > 0:
            logger.warning(
                f"Reusable bytes payload size ({len(_reusable_bytes_payload)} bytes) "
                f"is smaller than estimated size ({estimated_size} bytes), resizing."
            )
        logger.debug(f"Set reusable bytes payload to {estimated_size // ONE_KILOBYTE} kilobytes")
        _reusable_bytes_payload = bytearray(estimated_size)

    current_pos = 0

    # Add header with proper message type
    payload_header = np.recarray(1, dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    payload_header.message_type = MessageType.PAYLOAD_HEADER
    payload_header.frame_number = frame_number
    payload_header.number_of_cameras = number_of_cameras
    header_bytes = payload_header.tobytes()
    _reusable_bytes_payload[current_pos:current_pos + len(header_bytes)] = header_bytes
    current_pos += len(header_bytes)

    image_scale = 0.5
    frame_timestamps: list[float | np.floating] = []

    for camera_id in camera_ids:
        frame_recarray = latest_frames[camera_id]
        frame_timestamps.append(
            np.mean([
                frame_recarray.frame_metadata.timestamps.pre_frame_grab_ns,
                frame_recarray.frame_metadata.timestamps.post_frame_grab_ns
            ])
        )

        # Handle image rotation
        if frame_recarray.frame_metadata.camera_info.rotation != -1:
            t_rot0 = time.perf_counter()
            rotated_image = cv2.rotate(
                src=frame_recarray.image[0],
                rotateCode=frame_recarray.frame_metadata.camera_info.rotation[0]
            )
            if cg_id is not None:
                record_frontend_preview_timing_ms(
                    cg_id, str(camera_id), PREVIEW_TIMING_JPEG_ROTATE_MS,
                    (time.perf_counter() - t_rot0) * 1e3,
                )
        else:
            rotated_image = frame_recarray.image[0]

        # Calculate resize dimensions
        if display_image_sizes is None or camera_id not in display_image_sizes.keys():
            resize_image_height = int(rotated_image.shape[0] * image_scale)
            resize_image_width = int(rotated_image.shape[1] * image_scale)
        else:
            resize_image_height = int(display_image_sizes[camera_id]['height'])
            resize_image_width = int(display_image_sizes[camera_id]['width'])

        t_resize0 = time.perf_counter()
        resized_img = cv2.resize(
            src=rotated_image,
            dsize=(resize_image_width, resize_image_height),
            interpolation=cv2.INTER_LINEAR
        )
        if cg_id is not None:
            record_frontend_preview_timing_ms(
                cg_id, str(camera_id), PREVIEW_TIMING_JPEG_RESIZE_MS,
                (time.perf_counter() - t_resize0) * 1e3,
            )

        t_enc0 = time.perf_counter()
        _, jpeg_data = cv2.imencode(
            ext='.jpg',
            img=resized_img,
            params=jpeg_encoding_parameters
        )
        if cg_id is not None:
            record_frontend_preview_timing_ms(
                cg_id, str(camera_id), PREVIEW_TIMING_JPEG_ENCODE_MS,
                (time.perf_counter() - t_enc0) * 1e3,
            )
        jpeg_string = jpeg_data.tobytes()
        jpeg_string_length = len(jpeg_string)

        # Create frame header
        frame_header = np.recarray(1, dtype=FRONTEND_FRAME_HEADER_DTYPE)
        frame_header.message_type = MessageType.FRAME_HEADER
        frame_header.frame_number = frame_number
        frame_header.camera_id = camera_id.encode('utf-8')[:16]  # Truncate if necessary
        frame_header.camera_index = frame_recarray.frame_metadata.camera_info.camera_index[0]
        frame_header.color_channels = frame_recarray.frame_metadata.camera_info.color_channels[0]
        frame_header.image_width = resize_image_width
        frame_header.image_height = resize_image_height
        frame_header.jpeg_string_length = jpeg_string_length

        frame_header_bytes = frame_header.tobytes()

        # Ensure enough space
        required_size = current_pos + len(frame_header_bytes) + jpeg_string_length
        if required_size > len(_reusable_bytes_payload):
            old_size = len(_reusable_bytes_payload)
            _reusable_bytes_payload.extend(bytearray((required_size - old_size) + ONE_MEGABYTE))
            logger.warning(
                f"Payload size ({old_size} bytes) exceeded pre-allocated size, "
                f"resized to {len(_reusable_bytes_payload)} bytes"
            )

        # Copy data
        _reusable_bytes_payload[current_pos:current_pos + len(frame_header_bytes)] = frame_header_bytes
        current_pos += len(frame_header_bytes)
        _reusable_bytes_payload[current_pos:current_pos + jpeg_string_length] = jpeg_string
        current_pos += jpeg_string_length

    # Add footer with proper message type
    payload_footer = np.array(
        [(MessageType.PAYLOAD_FOOTER, frame_number, number_of_cameras)],
        dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE
    )
    footer_bytes = payload_footer.tobytes()

    if current_pos + len(footer_bytes) > len(_reusable_bytes_payload):
        og_len = len(_reusable_bytes_payload)
        _reusable_bytes_payload.extend(bytearray(len(footer_bytes)))
        logging.warning(
            f"Payload size ({og_len} bytes) exceeded pre-allocated size, "
            f"resized to {len(_reusable_bytes_payload)} bytes"
        )

    _reusable_bytes_payload[current_pos:current_pos + len(footer_bytes)] = footer_bytes
    current_pos += len(footer_bytes)

    frontend_bytes = _reusable_bytes_payload[:current_pos]

    if cg_id is not None:
        prepare_ms = (time.perf_counter() - t_ws_payload_prepare0) * 1e3
        for cid in camera_ids:
            record_frontend_preview_timing_ms(
                cg_id, str(cid), PREVIEW_TIMING_WS_PAYLOAD_PREPARE_MS, prepare_ms
            )

    return frame_number, np.mean(frame_timestamps), frontend_bytes
