"""Image-only callers share the live multiframe wire encoder."""

from dataclasses import replace

import cv2
import numpy as np
import pytest

from skellycam.core.types.frontend_payload_bytearray import (
    ImagePayloadFrame, ImagePayloadRequest, encode_image_payload,
    FRONTEND_FRAME_HEADER_DTYPE, FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE, MessageType,
)


def image_frame() -> ImagePayloadFrame:
    return ImagePayloadFrame(transport_id="view0", transport_index=0, frame_number=7,
        timestamp=1.25, image=np.full((40, 60, 3), 125, dtype=np.uint8),
        output_width=60, output_height=40)


def test_image_group_preserves_full_resolution_and_buffer_ownership() -> None:
    frame = image_frame()
    request = ImagePayloadRequest(frames=(frame, replace(frame, transport_id="view1", transport_index=1)),
        jpeg_encoding_parameters=(cv2.IMWRITE_JPEG_QUALITY, 90))
    ordinal, timestamp, payload = encode_image_payload(request)
    assert ordinal == 7
    assert timestamp == 1.25
    assert payload.readonly
    offset = FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
    for expected_index in range(2):
        header = np.frombuffer(payload, dtype=FRONTEND_FRAME_HEADER_DTYPE, count=1, offset=offset)[0]
        assert header["frame_number"] == 7
        assert header["camera_index"] == expected_index
        assert (header["image_width"], header["image_height"]) == (60, 40)
        offset += FRONTEND_FRAME_HEADER_DTYPE.itemsize
        length = int(header["jpeg_string_length"])
        pixels = cv2.imdecode(np.frombuffer(payload[offset:offset + length], dtype=np.uint8), cv2.IMREAD_COLOR)
        assert pixels.shape == frame.image.shape
        offset += length
    footer = np.frombuffer(payload, dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE, count=1, offset=offset)[0]
    assert footer["message_type"] == MessageType.PAYLOAD_FOOTER
    before = bytes(payload)
    frame.image.fill(0)
    encode_image_payload(request)
    assert bytes(payload) == before


@pytest.mark.parametrize("identity", ["", "x" * 17, "bad\0id", "ü"])
def test_invalid_transport_identity_fails_instead_of_truncating(identity: str) -> None:
    with pytest.raises(ValueError):
        replace(image_frame(), transport_id=identity)


def test_group_requires_equal_ordinals_and_unique_identity() -> None:
    frame = image_frame()
    for other in (frame, replace(frame, transport_id="view1"),
                  replace(frame, transport_id="view1", transport_index=1, frame_number=8)):
        with pytest.raises(ValueError):
            ImagePayloadRequest(frames=(frame, other), jpeg_encoding_parameters=())
