"""Arbitrary requested frame indices must match decoding the file from its beginning."""

from pathlib import Path
import os
from unittest.mock import patch

import av
import cv2
import numpy as np
import pytest

from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader, SequentialVideoReaders


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    path = tmp_path / "frames.mp4"
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("libx264", rate=30)
        stream.width = 64
        stream.height = 48
        stream.pix_fmt = "yuv420p"
        for index in range(20):
            pixels = np.full((48, 64, 3), index * 10, dtype=np.uint8)
            pixels[:, index:index + 5, 1] = 255
            frame = av.VideoFrame.from_ndarray(pixels, format="bgr24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_forward_backward_and_repeated_requests(video_path: Path) -> None:
    path = video_path
    with av.open(str(path)) as container:
        expected = [cv2.imencode('.jpg', frame.to_ndarray(format='bgr24'))[1].tobytes()
                    for frame in container.decode(video=0)]
    readers = SequentialVideoReaders(capacity=1, cache_bytes=1024 * 1024)
    try:
        for index in (0, 15, 3, 19, 0, 3, 3):
            assert readers.read_jpeg(path=path, frame_number=index) == expected[index]
        with pytest.raises(IndexError, match="ends before"):
            readers.read_jpeg(path=path, frame_number=20)
        assert readers.read_jpeg(path=path, frame_number=2) == expected[2]
        with pytest.raises(ValueError, match="nonnegative"):
            readers.read_jpeg(path=path, frame_number=-1)
    finally:
        readers.close()


def test_cached_backward_frame_does_not_move_decoder(video_path: Path) -> None:
    readers = SequentialVideoReaders(capacity=1, cache_bytes=1024 * 1024)
    try:
        first = readers.read_jpeg(path=video_path, frame_number=0)
        readers.read_jpeg(path=video_path, frame_number=10)
        reader = next(iter(readers.readers.values()))
        with patch.object(reader, "read_jpeg", side_effect=AssertionError("Cache hit decoded a frame")):
            assert readers.read_jpeg(path=video_path, frame_number=0) == first
        assert reader.frame_number == 10
        readers.read_jpeg(path=video_path, frame_number=11)
        assert reader.frame_number == 11
    finally:
        readers.close()


def test_lru_eviction_and_byte_budget(video_path: Path) -> None:
    reference = SequentialVideoReader(path=video_path)
    try:
        images = [reference.read_jpeg(frame_number=index) for index in range(3)]
    finally:
        reference.close()
    sizes = [len(image) for image in images]
    budget = sum(sizes) - min(sizes)
    readers = SequentialVideoReaders(capacity=1, cache_bytes=budget)
    try:
        for index in (0, 1, 0, 2):
            assert readers.read_jpeg(path=video_path, frame_number=index) == images[index]
            assert readers.cached_bytes <= budget
        assert [key.frame_number for key in readers.cache] == [0, 2]
        assert readers.read_jpeg(path=video_path, frame_number=1) == images[1]
        assert next(iter(readers.readers.values())).frame_number == 1
        assert readers.cached_bytes == sum(len(image) for image in readers.cache.values())
    finally:
        readers.close()
    assert readers.cached_bytes == 0 and not readers.cache


def test_cache_survives_decoder_eviction(video_path: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.mp4"
    other.write_bytes(video_path.read_bytes())
    readers = SequentialVideoReaders(capacity=1, cache_bytes=1024 * 1024)
    try:
        first = readers.read_jpeg(path=video_path, frame_number=0)
        readers.read_jpeg(path=other, frame_number=1)
        with patch.object(SequentialVideoReader, "__init__", side_effect=AssertionError("Cache hit opened a decoder")):
            assert readers.read_jpeg(path=video_path, frame_number=0) == first
    finally:
        readers.close()


def test_oversized_image_is_not_cached(video_path: Path) -> None:
    readers = SequentialVideoReaders(capacity=1, cache_bytes=1)
    try:
        assert len(readers.read_jpeg(path=video_path, frame_number=0)) > 1
        assert not readers.cache and readers.cached_bytes == 0
    finally:
        readers.close()


def test_changed_file_identity_does_not_reuse_cached_frame(video_path: Path) -> None:
    readers = SequentialVideoReaders(capacity=1, cache_bytes=1024 * 1024)
    try:
        readers.read_jpeg(path=video_path, frame_number=0)
        previous = next(iter(readers.readers.values()))
        stat = video_path.stat()
        os.utime(video_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        readers.read_jpeg(path=video_path, frame_number=0)
        assert next(iter(readers.readers.values())) is not previous
        assert len(readers.cache) == 2
    finally:
        readers.close()
