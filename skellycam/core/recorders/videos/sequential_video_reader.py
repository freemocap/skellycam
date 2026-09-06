"""Frame-indexed decoding that advances through every intervening video frame."""

from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import av
from av.container import InputContainer
from av.video.frame import VideoFrame
import cv2
import numpy as np


class SequentialVideoReader:
    def __init__(self, *, path: Path) -> None:
        self.path = path
        self.container: InputContainer = av.open(str(path))
        self.frames: Iterator[VideoFrame] = iter(self.container.decode(video=0))
        self.frame_number = -1
        self.image: bytes | None = None
        self.frame: VideoFrame | None = None

    def close(self) -> None:
        self.container.close()

    def read_bgr(self, *, frame_number: int) -> np.ndarray:
        if frame_number < 0:
            raise ValueError("Frame number must be nonnegative")
        if frame_number < self.frame_number:
            self.close()
            self.container = av.open(str(self.path))
            self.frames = iter(self.container.decode(video=0))
            self.frame_number = -1
            self.image = None
            self.frame = None
        while self.frame_number < frame_number:
            try:
                self.frame = next(self.frames)
            except StopIteration as error:
                raise IndexError(f"Video {self.path} ends before frame {frame_number}") from error
            self.frame_number += 1
            self.image = None
        if self.frame is None:
            raise RuntimeError("Decoder did not produce the requested frame")
        if self.frame.is_corrupt:
            raise RuntimeError(f"Corrupt video frame {frame_number} in {self.path}")
        rotation = self.frame.rotation
        if rotation % 90:
            raise ValueError(f"Unsupported video display rotation: {rotation}")
        pixels = self.frame.to_ndarray(format='bgr24')
        return np.ascontiguousarray(np.rot90(pixels, k=rotation // 90))

    def read_jpeg(self, *, frame_number: int) -> bytes:
        if frame_number != self.frame_number or self.image is None:
            pixels = self.read_bgr(frame_number=frame_number)
            success, encoded = cv2.imencode('.jpg', pixels)
            if not success:
                raise RuntimeError(f"Unable to encode {self.path} frame {frame_number}")
            self.image = encoded.tobytes()
        if self.image is None:
            raise RuntimeError("Decoder did not produce the requested frame")
        return self.image


@dataclass(frozen=True, slots=True)
class VideoFileIdentity:
    path: Path
    size: int
    modified_ns: int
    inode: int

    @classmethod
    def from_path(cls, *, path: Path) -> "VideoFileIdentity":
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
        return cls(path=resolved, size=stat.st_size, modified_ns=stat.st_mtime_ns, inode=stat.st_ino)


@dataclass(frozen=True, slots=True)
class VideoFrameKey:
    video: VideoFileIdentity
    frame_number: int


class SequentialVideoReaders:
    """Bound open decoders; serialize requests so a reader's frame counter remains authoritative."""

    def __init__(self, *, capacity: int, cache_bytes: int) -> None:
        if capacity < 1:
            raise ValueError("Decoder capacity must be positive")
        if cache_bytes < 1:
            raise ValueError("Frame cache byte budget must be positive")
        self.capacity = capacity
        self.cache_budget_bytes = cache_bytes
        self.cached_bytes = 0
        self.cache: OrderedDict[VideoFrameKey, bytes] = OrderedDict()
        self.readers: OrderedDict[VideoFileIdentity, SequentialVideoReader] = OrderedDict()
        self.lock = Lock()

    def read_jpeg(self, *, path: Path, frame_number: int) -> bytes:
        if frame_number < 0:
            raise ValueError("Frame number must be nonnegative")
        key = VideoFileIdentity.from_path(path=path)
        frame_key = VideoFrameKey(video=key, frame_number=frame_number)
        with self.lock:
            cached = self.cache.get(frame_key)
            if cached is not None:
                self.cache.move_to_end(frame_key)
                return cached
            reader = self.readers.pop(key, None)
            if reader is None:
                while len(self.readers) >= self.capacity:
                    _, evicted = self.readers.popitem(last=False)
                    evicted.close()
                reader = SequentialVideoReader(path=key.path)
            self.readers[key] = reader
            try:
                image = reader.read_jpeg(frame_number=frame_number)
                if len(image) <= self.cache_budget_bytes:
                    while self.cached_bytes + len(image) > self.cache_budget_bytes:
                        _, evicted_image = self.cache.popitem(last=False)
                        self.cached_bytes -= len(evicted_image)
                    self.cache[frame_key] = image
                    self.cached_bytes += len(image)
                return image
            except Exception:
                self.readers.pop(key).close()
                raise

    def close(self) -> None:
        with self.lock:
            for reader in self.readers.values():
                reader.close()
            self.readers.clear()
            self.cache.clear()
            self.cached_bytes = 0
