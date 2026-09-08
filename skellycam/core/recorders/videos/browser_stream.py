"""Pull-driven, video-only H.264 fragments for browser playback."""

from collections.abc import Generator
from dataclasses import dataclass, field
from fractions import Fraction
from math import isfinite
from pathlib import Path

import av


@dataclass(frozen=True)
class BrowserStreamRequest:
    path: Path
    start_seconds: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if not isfinite(self.start_seconds) or self.start_seconds < 0:
            raise ValueError("Playback start must be finite and nonnegative")
        if not isfinite(self.duration_seconds) or self.duration_seconds <= 0:
            raise ValueError("Playback duration must be finite and positive")


@dataclass
class FragmentBuffer:
    """Non-seekable output, drained after each encoded frame."""

    data: bytearray = field(default_factory=bytearray)
    limit_bytes: int = 8 * 1024 * 1024

    def write(self, data: bytes) -> int:
        if len(self.data) + len(data) > self.limit_bytes:
            raise BufferError("Encoded video fragment exceeds the playback buffer limit")
        self.data.extend(data)
        return len(data)

    def drain(self) -> bytes:
        result = bytes(self.data)
        self.data.clear()
        return result


def browser_video_chunks(*, request: BrowserStreamRequest) -> Generator[bytes, None, None]:
    """Encode on demand; closing the iterator releases both codec containers.

    Seeking uses source timestamps for approximate viewing. Output starts at zero.
    This is not a frame-indexed processing reader. No output files are created.
    """
    with av.open(str(request.path)) as source:
        if len(source.streams.video) != 1:
            raise ValueError("Browser playback requires exactly one video track per file")
        video = source.streams.video[0]
        if video.time_base is None or video.average_rate is None:
            raise ValueError("Video is missing its time base or nominal frame rate")
        origin = video.start_time or 0
        start = origin + int(request.start_seconds / video.time_base)
        source.seek(start, stream=video, backward=True)
        frames = source.decode(video)
        first = None
        for candidate in frames:
            if candidate.pts is None or candidate.is_corrupt:
                raise ValueError("Video contains a corrupt frame or missing presentation timestamp")
            if candidate.pts >= start:
                first = candidate
                break
        if first is None:
            raise ValueError("Playback start is beyond the available video")
        if first.rotation != 0:
            raise ValueError("The browser streaming prototype does not yet apply video rotation")
        scale = min(1.0, 1280 / first.width, 720 / first.height)
        width = max(2, int(first.width * scale) // 2 * 2)
        height = max(2, int(first.height * scale) // 2 * 2)
        sink = FragmentBuffer()
        with av.open(sink, mode="w", format="mp4", options={
            "movflags": "frag_keyframe+empty_moov+default_base_moof",
            "frag_duration": "250000",
        }) as output:
            encoded = output.add_stream("libx264", rate=video.average_rate)
            encoded.width = width
            encoded.height = height
            encoded.pix_fmt = "yuv420p"
            encoded.time_base = Fraction(1, 90000)
            encoded.codec_context.thread_count = 2
            encoded.codec_context.max_b_frames = 0
            encoded.options = {"preset": "ultrafast", "tune": "zerolatency", "crf": "23", "profile": "baseline"}
            output.start_encoding()
            yield sink.drain()
            first_time = first.pts * video.time_base
            frame = first
            while frame is not None:
                if frame.pts is None or frame.is_corrupt:
                    raise ValueError("Video contains a corrupt frame or missing presentation timestamp")
                elapsed = frame.pts * video.time_base - first_time
                if elapsed >= Fraction(str(request.duration_seconds)):
                    break
                converted = frame.reformat(width=width, height=height, format="yuv420p")
                converted.pts = round(elapsed * 90000)
                converted.time_base = Fraction(1, 90000)
                for packet in encoded.encode(converted):
                    output.mux(packet)
                if sink.data:
                    yield sink.drain()
                frame = next(frames, None)
            for packet in encoded.encode():
                output.mux(packet)
        if sink.data:
            yield sink.drain()
