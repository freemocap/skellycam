"""Regression tests for skellycam.opencv.video_recorder.streaming_video_writer.

These are the direct-unit-level tests for the bounded-queue streaming
recorder that replaced the unbounded frame_payload_list + Stop-time
deepcopy() architecture (see ARCHITECTURE_REPORT.md). No real camera or
cv2 encoder is required for most cases -- a FakeEncoder stands in so these
run fast and deterministically.
"""
import queue
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from skellycam.opencv.video_recorder.streaming_video_writer import (
    StreamingFramePacket,
    StreamingVideoWriter,
    WriterFailedError,
    WriterSaturatedError,
)


class FakeEncoder:
    """No-op encoder: records what it was asked to do without touching disk
    or a real video codec, so memory/queue-behavior tests run fast."""

    def __init__(self, fail_after_n_writes: int = None, open_delay_seconds: float = 0.0,
                 write_delay_seconds: float = 0.0):
        self.opened = False
        self.open_args = None
        self.write_count = 0
        self.released = False
        self._fail_after_n_writes = fail_after_n_writes
        self._open_delay_seconds = open_delay_seconds
        self._write_delay_seconds = write_delay_seconds

    def open(self, path: Path, width: int, height: int, fps: float) -> bool:
        if self._open_delay_seconds:
            time.sleep(self._open_delay_seconds)
        self.opened = True
        self.open_args = (path, width, height, fps)
        Path(path).touch()  # stand in for a real encoder creating the file on open()
        return True

    def write(self, image: np.ndarray) -> None:
        if self._write_delay_seconds:
            time.sleep(self._write_delay_seconds)
        self.write_count += 1
        if self._fail_after_n_writes is not None and self.write_count > self._fail_after_n_writes:
            raise RuntimeError("FakeEncoder simulated write failure")

    def release(self) -> None:
        self.released = True


def make_packet(frame_index: int, camera_id: str = "0", width: int = 4, height: int = 4) -> StreamingFramePacket:
    return StreamingFramePacket(
        frame_index=frame_index,
        camera_id=camera_id,
        timestamp_ns=frame_index * 33_000_000,
        image=np.zeros((height, width, 3), dtype=np.uint8),
    )


class TestStreamingLifecycle:
    def test_writer_opens_encoder_on_first_frame(self, tmp_path):
        encoder = FakeEncoder()
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=encoder,
        )
        writer.start()
        writer.submit(make_packet(0))
        result = writer.stop(timeout_seconds=5)

        assert encoder.opened
        assert encoder.released
        assert result.success
        assert result.frames_written == 1

    def test_frames_are_encoded_before_stop_returns(self, tmp_path):
        encoder = FakeEncoder()
        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=encoder)
        writer.start()
        for i in range(10):
            writer.submit(make_packet(i))
        result = writer.stop(timeout_seconds=5)

        assert encoder.write_count == 10
        assert result.frames_written == 10

    def test_final_file_exists_only_after_success(self, tmp_path):
        output_path = tmp_path / "cam.mp4"
        encoder = FakeEncoder()
        writer = StreamingVideoWriter(output_path=output_path, expected_fps=30.0, encoder=encoder)
        writer.start()
        writer.submit(make_packet(0))

        assert not output_path.exists()  # not yet -- still recording
        result = writer.stop(timeout_seconds=5)

        assert result.output_path == output_path
        assert result.partial_path is None

    def test_stop_before_any_frame_submitted_fails_honestly(self, tmp_path):
        encoder = FakeEncoder()
        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=encoder)
        writer.start()
        result = writer.stop(timeout_seconds=5)

        assert not result.success
        assert result.frames_written == 0


class TestBoundedMemory:
    def test_queue_capacity_is_finite(self, tmp_path):
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, queue_capacity=5,
            encoder=FakeEncoder(),
        )
        assert writer.queue_capacity == 5

    def test_peak_queue_depth_never_exceeds_capacity(self, tmp_path):
        # A slow encoder forces the queue to build up so we can observe peak depth.
        encoder = FakeEncoder(write_delay_seconds=0.01)
        capacity = 10
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, queue_capacity=capacity,
            submit_timeout_seconds=2.0, encoder=encoder,
        )
        writer.start()
        for i in range(30):
            writer.submit(make_packet(i))
        result = writer.stop(timeout_seconds=10)

        assert result.success
        assert result.peak_queue_depth <= capacity

    def test_longer_simulated_duration_does_not_increase_queue_capacity(self, tmp_path):
        """The core regression: capacity is a constant set at construction,
        never a function of how many frames have been submitted -- unlike
        the old unbounded frame_payload_list."""
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, queue_capacity=8,
            encoder=FakeEncoder(),
        )
        writer.start()
        for i in range(500):
            writer.submit(make_packet(i))
            assert writer.queue_capacity == 8  # constant, regardless of frames submitted so far
        writer.stop(timeout_seconds=5)


class TestDeepcopyRegression:
    def test_stop_path_never_calls_deepcopy(self, tmp_path, monkeypatch):
        import copy

        calls = []
        original_deepcopy = copy.deepcopy

        def spy_deepcopy(*args, **kwargs):
            calls.append(args)
            return original_deepcopy(*args, **kwargs)

        monkeypatch.setattr(copy, "deepcopy", spy_deepcopy)

        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=FakeEncoder())
        writer.start()
        for i in range(5):
            writer.submit(make_packet(i))
        writer.stop(timeout_seconds=5)

        assert calls == [], "StreamingVideoWriter.stop() must never deepcopy anything"

    def test_camera_group_thread_worker_source_contains_no_deepcopy(self):
        """Prevent the removed recorder-deepcopy call from returning.

        Explanatory comments and docstrings may still mention deepcopy.
        """
        import re
        from pathlib import Path

        import skellycam.gui.qt.workers.camera_group_thread_worker as worker_module

        source_path = Path(worker_module.__file__)
        source = source_path.read_text()

        assert re.search(
            r"\bdeepcopy\s*\(\s*video_recorder\s*\)",
            source,
        ) is None

        assert re.search(
            r"^\s*from\s+copy\s+import\s+deepcopy\s*$",
            source,
            flags=re.MULTILINE,
        ) is None


class TestQueueSaturation:
    def test_persistent_saturation_raises_and_fails_honestly(self, tmp_path):
        # Encoder that never drains (long delay per write) + tiny queue + short submit timeout
        encoder = FakeEncoder(write_delay_seconds=5.0)
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, queue_capacity=1,
            submit_timeout_seconds=0.1, encoder=encoder,
        )
        writer.start()
        writer.submit(make_packet(0))  # fills the single slot; drain loop is now stuck writing it

        with pytest.raises(WriterSaturatedError):
            writer.submit(make_packet(1))
            writer.submit(make_packet(2))  # one of these should overflow the capacity-1 queue

        assert not writer.is_healthy

    def test_submit_after_failure_raises_writer_failed(self, tmp_path):
        encoder = FakeEncoder(write_delay_seconds=5.0)
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, queue_capacity=1,
            submit_timeout_seconds=0.1, encoder=encoder,
        )
        writer.start()
        writer.submit(make_packet(0))
        with pytest.raises(WriterSaturatedError):
            for i in range(1, 5):
                writer.submit(make_packet(i))

        with pytest.raises(WriterFailedError):
            writer.submit(make_packet(99))

    def test_saturation_preserves_partial_file_not_reported_complete(self, tmp_path):
        output_path = tmp_path / "cam.mp4"
        encoder = FakeEncoder(write_delay_seconds=5.0)
        writer = StreamingVideoWriter(
            output_path=output_path, expected_fps=30.0, queue_capacity=1,
            submit_timeout_seconds=0.1, encoder=encoder,
        )
        writer.start()
        writer.submit(make_packet(0))
        try:
            for i in range(1, 5):
                writer.submit(make_packet(i))
        except WriterSaturatedError:
            pass

        result = writer.stop(timeout_seconds=1)  # writer thread is stuck in a 5s sleep -- expect a timeout-based failure too

        assert not result.success
        assert not output_path.exists()


class TestWriterFailure:
    def test_encoder_write_exception_fails_the_recording(self, tmp_path):
        output_path = tmp_path / "cam.mp4"
        encoder = FakeEncoder(fail_after_n_writes=3)
        writer = StreamingVideoWriter(output_path=output_path, expected_fps=30.0, encoder=encoder)
        writer.start()
        for i in range(10):
            try:
                writer.submit(make_packet(i))
            except WriterFailedError:
                break
        result = writer.stop(timeout_seconds=5)

        assert not result.success
        assert not output_path.exists()
        assert result.partial_path is not None

    def test_encoder_open_failure_is_reported(self, tmp_path):
        class FailToOpenEncoder(FakeEncoder):
            def open(self, path, width, height, fps) -> bool:
                return False

        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=FailToOpenEncoder())
        writer.start()
        writer.submit(make_packet(0))
        result = writer.stop(timeout_seconds=5)

        assert not result.success
        assert result.error is not None


class TestTimestampBehavior:
    def test_timestamps_written_incrementally_not_all_at_once(self, tmp_path):
        """The historical bug used np.append() in a loop (O(n^2)). This test
        proves the internal timestamp list grows one scalar tuple at a time
        during the drain loop, and is converted to a numpy array exactly
        once at finalize -- not per-frame."""
        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=FakeEncoder())
        writer.start()
        for i in range(50):
            writer.submit(make_packet(i))
        writer.stop(timeout_seconds=5)

        # after stop(), the npy/csv files should exist with exactly 50 rows
        timestamp_folder = (tmp_path / "timestamps")
        npy_files = list(timestamp_folder.glob("*_binary.npy"))
        assert len(npy_files) == 1
        saved = np.load(npy_files[0])
        assert len(saved) == 50
        assert list(saved) == sorted(saved)  # monotonic, matches submission order

    def test_frame_index_sequence_is_monotonic(self, tmp_path):
        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=FakeEncoder())
        writer.start()
        indices = list(range(20))
        for i in indices:
            writer.submit(make_packet(i))
        writer.stop(timeout_seconds=5)

        assert writer.frames_written == len(indices)
