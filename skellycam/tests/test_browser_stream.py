from io import BytesIO
from pathlib import Path

import av
import numpy as np
import pytest

from skellycam.core.recorders.videos.browser_stream import BrowserStreamRequest, FragmentBuffer, browser_video_chunks


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    path = tmp_path / "numbered_video.mp4"
    with av.open(str(path), mode="w") as container:
        stream = container.add_stream("mpeg4", rate=30)
        stream.width = 160
        stream.height = 120
        stream.pix_fmt = "yuv420p"
        for index in range(90):
            frame = av.VideoFrame.from_ndarray(np.full((120, 160, 3), index * 2, dtype=np.uint8), format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


@pytest.mark.parametrize("start", [0.0, 1.0, 2.0])
def test_fragments_decode_with_rebased_timestamps(video_path: Path, start: float) -> None:
    chunks = list(browser_video_chunks(request=BrowserStreamRequest(
        path=video_path, start_seconds=start, duration_seconds=0.8)))
    assert len(chunks) > 2
    assert b"moov" in chunks[0]
    assert any(b"moof" in chunk for chunk in chunks[1:])
    with av.open(BytesIO(b"".join(chunks))) as output:
        frames = list(output.decode(video=0))
        assert len(frames) == 24
        assert frames[0].time == 0
        assert abs(float(frames[0].to_ndarray(format="rgb24").mean()) - start * 60) < 5
        assert output.streams.video[0].codec_context.name == "h264"


def test_cancel_and_restart_without_output_files(video_path: Path) -> None:
    files = set(video_path.parent.iterdir())
    chunks = browser_video_chunks(request=BrowserStreamRequest(path=video_path, start_seconds=0.0, duration_seconds=3.0))
    assert next(chunks)
    assert next(chunks)
    chunks.close()
    assert set(video_path.parent.iterdir()) == files
    test_fragments_decode_with_rebased_timestamps(video_path=video_path, start=1.0)


def test_fragment_memory_limit() -> None:
    sink = FragmentBuffer(limit_bytes=8)
    sink.write(b"12345678")
    with pytest.raises(BufferError):
        sink.write(b"9")
    assert sink.drain() == b"12345678"
    assert not sink.data


def test_unavailable_start_fails_before_header(video_path: Path) -> None:
    chunks = browser_video_chunks(request=BrowserStreamRequest(path=video_path, start_seconds=100.0, duration_seconds=1.0))
    with pytest.raises(ValueError, match="beyond"):
        next(chunks)
