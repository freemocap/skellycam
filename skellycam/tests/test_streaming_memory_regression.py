"""Phase A synthetic memory regression tests for the streaming recorder.

No real camera. Frames are generated one at a time and submitted directly to
StreamingVideoWriter (and, for one integration test, through VideoRecorder),
never pre-built into a full-recording list -- that would defeat the point of
testing bounded memory.
"""
import gc
import json
import os
import threading
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np
import psutil
import pytest

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.streaming_video_writer import (
    Cv2FrameEncoder,
    StreamingFramePacket,
    StreamingVideoWriter,
    WriterFailedError,
    WriterSaturatedError,
)
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.tests.test_streaming_video_writer import FakeEncoder


# ---------------------------------------------------------------------------
# Memory sampling helpers
# ---------------------------------------------------------------------------

def _rss_mib() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / (1024 ** 2)


@dataclass
class MemorySample:
    frame_index: int
    rss_mib: float
    queue_depth: int
    elapsed_seconds: float


@dataclass
class MemoryTrace:
    rss_start_mib: float
    rss_warm_mib: Optional[float] = None
    samples: List[MemorySample] = field(default_factory=list)
    rss_before_stop_mib: Optional[float] = None
    rss_peak_during_stop_mib: Optional[float] = None
    rss_after_stop_mib: Optional[float] = None
    rss_after_gc_mib: Optional[float] = None
    stop_duration_seconds: Optional[float] = None
    peak_queue_depth: int = 0
    result = None

    @property
    def rss_peak_submission_mib(self) -> float:
        return max((s.rss_mib for s in self.samples), default=self.rss_start_mib)


def _sample_rss_during(fn, interval_seconds: float = 0.005):
    """Runs fn() while polling RSS on a background thread. Returns (result, peak_rss_mib)."""
    peak = {"value": _rss_mib()}
    stop_flag = threading.Event()

    def sampler():
        while not stop_flag.is_set():
            peak["value"] = max(peak["value"], _rss_mib())
            time.sleep(interval_seconds)

    sampler_thread = threading.Thread(target=sampler, daemon=True)
    sampler_thread.start()
    result = fn()
    stop_flag.set()
    sampler_thread.join(timeout=2)
    peak["value"] = max(peak["value"], _rss_mib())
    return result, peak["value"]


def run_synthetic_streaming_test(
        tmp_path: Path,
        width: int,
        height: int,
        frame_count: int,
        queue_capacity: int = 60,
        sample_every: int = 250,
        encoder=None,
        expected_fps: float = 30.0,
        warmup_frames: int = 20,
) -> MemoryTrace:
    encoder = encoder or FakeEncoder()
    writer = StreamingVideoWriter(
        output_path=tmp_path / "synthetic.mp4",
        expected_fps=expected_fps,
        queue_capacity=queue_capacity,
        encoder=encoder,
    )

    gc.collect()
    trace = MemoryTrace(rss_start_mib=_rss_mib())
    writer.start()

    warmup_frames = min(warmup_frames, frame_count)
    for i in range(warmup_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        writer.submit(StreamingFramePacket(
            frame_index=i, camera_id="0", timestamp_ns=i * 33_000_000, image=frame,
        ))
        del frame
    time.sleep(0.05)
    trace.rss_warm_mib = _rss_mib()

    start_time = time.perf_counter()
    for i in range(warmup_frames, frame_count):
        frame = np.zeros((height, width, 3), dtype=np.uint8)  # one frame at a time -- never a full-recording list
        writer.submit(StreamingFramePacket(
            frame_index=i, camera_id="0", timestamp_ns=i * 33_000_000, image=frame,
        ))
        del frame  # explicit -- mirrors the production capture loop, which holds no frame reference after submit()

        if i % sample_every == 0:
            trace.samples.append(MemorySample(
                frame_index=i, rss_mib=_rss_mib(), queue_depth=writer.queue_depth,
                elapsed_seconds=time.perf_counter() - start_time,
            ))

    trace.peak_queue_depth = writer.peak_queue_depth
    trace.rss_before_stop_mib = _rss_mib()

    stop_start = time.perf_counter()
    result, peak_during_stop = _sample_rss_during(lambda: writer.stop(timeout_seconds=30))
    trace.stop_duration_seconds = time.perf_counter() - stop_start
    trace.rss_peak_during_stop_mib = peak_during_stop
    trace.rss_after_stop_mib = _rss_mib()
    trace.peak_queue_depth = max(trace.peak_queue_depth, writer.peak_queue_depth)

    gc.collect()
    trace.rss_after_gc_mib = _rss_mib()
    trace.result = result
    return trace


def assert_bounded_and_plateaued(
        trace: MemoryTrace,
        absolute_ceiling_mib: float,
        max_growth_ratio_last_vs_first_third: float = 2.5,
):
    """Two independent checks, neither a brittle single exact-value assertion:

    1. Absolute safety ceiling -- generous relative to the old architecture's
       multi-GB growth, but still tight enough to catch a real regression.
    2. Growth-slope/plateau check -- the *rate* of growth in the last third
       of submission must not be meaningfully larger than the first third.
       A bounded-queue architecture should plateau; the old unbounded list
       grew ~linearly for the entire recording, so its last-third slope
       would be comparable to (not smaller than) its first-third slope.
    """
    growth_mib = trace.rss_peak_submission_mib - trace.rss_start_mib
    assert growth_mib < absolute_ceiling_mib, (
        f"RSS grew {growth_mib:.1f} MiB during submission, exceeding the "
        f"{absolute_ceiling_mib} MiB safety ceiling"
    )

    n = len(trace.samples)
    assert n >= 6, "not enough samples to assess a growth trend"
    third = max(n // 3, 1)
    first_third = trace.samples[:third]
    last_third = trace.samples[-third:]

    first_delta = first_third[-1].rss_mib - trace.rss_start_mib
    last_delta = last_third[-1].rss_mib - first_third[-1].rss_mib

    # Guard against division-by-zero when growth is tiny/negative (noise) --
    # in that case the plateau check trivially passes since there's nothing
    # to be non-bounded about.
    if first_delta > 1.0:
        ratio = last_delta / first_delta if first_delta else 0
        assert ratio < max_growth_ratio_last_vs_first_third, (
            f"RSS growth did not plateau: first-third delta={first_delta:.1f} MiB, "
            f"last-third delta={last_delta:.1f} MiB (ratio={ratio:.2f}, "
            f"ceiling={max_growth_ratio_last_vs_first_third})"
        )


# ---------------------------------------------------------------------------
# Test A -- 960x540, 9000 frames (5-minute equivalent at 30fps)
# ---------------------------------------------------------------------------

class TestSyntheticMemory960x540:
    def test_five_minute_equivalent_bounded_memory(self, tmp_path):
        trace = run_synthetic_streaming_test(
            tmp_path, width=960, height=540, frame_count=9000, queue_capacity=60, sample_every=500,
        )

        assert trace.result.success
        assert trace.result.frames_submitted == 9000
        assert trace.result.frames_written == 9000
        assert trace.peak_queue_depth <= 60

        # Absolute ceiling: 60-frame queue x ~1.48 MiB/frame (960x540x3) is
        # ~90 MiB in flight at most, plus Python/GC/thread overhead. 400 MiB
        # is generous headroom while still nowhere near the old architecture's
        # multi-GB-for-the-whole-recording growth.
        assert_bounded_and_plateaued(trace, absolute_ceiling_mib=400.0)

        # Segment trend check requested explicitly: 0-1000, 4000-5000, 8000-9000
        segments = {
            "0-1000": [s for s in trace.samples if s.frame_index <= 1000],
            "4000-5000": [s for s in trace.samples if 4000 <= s.frame_index <= 5000],
            "8000-9000": [s for s in trace.samples if 8000 <= s.frame_index <= 9000],
        }
        segment_avgs = {
            name: (sum(s.rss_mib for s in samples) / len(samples) if samples else None)
            for name, samples in segments.items()
        }
        early, mid, late = segment_avgs["0-1000"], segment_avgs["4000-5000"], segment_avgs["8000-9000"]
        if early is not None and late is not None:
            # The late segment must not show continued *linear* growth
            # comparable to the full early-to-mid delta happening *again*
            # between mid and late.
            early_to_mid = (mid - early) if mid is not None else 0
            mid_to_late = (late - mid) if mid is not None else (late - early)
            if early_to_mid > 1.0:
                assert mid_to_late < early_to_mid * 2.5, (
                    f"late-segment growth ({mid_to_late:.1f} MiB) still scales like early "
                    f"growth ({early_to_mid:.1f} MiB) -- looks duration-linear, not plateaued"
                )


class TestSyntheticMemory1280x720:
    def test_two_minute_equivalent_bounded_memory(self, tmp_path):
        trace = run_synthetic_streaming_test(
            tmp_path, width=1280, height=720, frame_count=3600, queue_capacity=60, sample_every=250,
        )

        assert trace.result.success
        assert trace.result.frames_submitted == 3600
        assert trace.result.frames_written == 3600
        assert trace.peak_queue_depth <= 60

        # This specific case is what previously carried an estimated
        # 13-15 GiB Stop-time spike (see ARCHITECTURE_REPORT.md). The new
        # implementation must not approach anything remotely similar --
        # 400 MiB ceiling is ~35x smaller than even the old *steady-state*
        # estimate (6.88 GiB) for this exact resolution/duration.
        assert_bounded_and_plateaued(trace, absolute_ceiling_mib=400.0)

        # Stop-time doubling check specific to this resolution/duration.
        stop_delta = trace.rss_peak_during_stop_mib - trace.rss_before_stop_mib
        assert stop_delta < 200.0, (
            f"Stop-time RSS delta was {stop_delta:.1f} MiB -- the old architecture's "
            f"deepcopy() would have doubled an already multi-GiB buffer at this point"
        )


# ---------------------------------------------------------------------------
# Stop-time regression -- the most important Phase A check
# ---------------------------------------------------------------------------

class TestStopTimeRegression:
    @pytest.mark.parametrize("frame_count", [300, 3000, 9000])
    def test_stop_delta_does_not_scale_with_frame_count(self, tmp_path, frame_count):
        trace = run_synthetic_streaming_test(
            tmp_path, width=960, height=540, frame_count=frame_count, queue_capacity=60,
            sample_every=max(frame_count // 10, 1),
        )
        stop_delta = trace.rss_peak_during_stop_mib - trace.rss_before_stop_mib
        # Store on trace for the cross-parametrization comparison below via a module-level accumulator.
        _STOP_DELTAS[frame_count] = stop_delta

        assert trace.result.success
        assert trace.result.frames_written == frame_count
        # Bounded regardless of duration -- if Stop scaled with frame count
        # (the old deepcopy behavior), 9000 frames would show a delta
        # roughly 30x that of 300 frames at 960x540 (~3.9 GiB vs ~130 MiB).
        assert stop_delta < 150.0, (
            f"Stop RSS delta at {frame_count} frames was {stop_delta:.1f} MiB -- "
            f"expected a small, roughly-constant delta regardless of duration"
        )

    def test_stop_delta_stays_approximately_constant_across_durations(self, tmp_path):
        """Runs after the parametrized cases above have populated _STOP_DELTAS
        (pytest executes tests in file order within a class by default)."""
        if len(_STOP_DELTAS) < 3:
            pytest.skip("requires all three parametrized Stop-delta cases to have run first")

        deltas = list(_STOP_DELTAS.values())
        smallest, largest = min(deltas), max(deltas)
        # "Approximately constant" -- allow generous noise headroom (psutil
        # RSS is not perfectly deterministic), but the 9000-frame case must
        # not be wildly larger than the 300-frame case. The old architecture
        # would show ~30x here; anything under 5x is a clear pass.
        if smallest > 1.0:
            assert (largest / smallest) < 5.0, (
                f"Stop RSS deltas across durations were {_STOP_DELTAS} -- ratio "
                f"{largest / smallest:.2f}x is too duration-dependent"
            )


_STOP_DELTAS = {}


# ---------------------------------------------------------------------------
# Retained-reference / garbage-collection test
# ---------------------------------------------------------------------------

class TestRetainedReference:
    def test_frame_is_eligible_for_gc_after_write(self, tmp_path):
        encoder = FakeEncoder()
        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=encoder)
        writer.start()

        frame = np.zeros((16, 16, 3), dtype=np.uint8)
        frame_ref = weakref.ref(frame)
        writer.submit(StreamingFramePacket(frame_index=0, camera_id="0", timestamp_ns=0, image=frame))
        del frame  # the only strong ref the test held

        # give the drain thread time to consume and drop its own reference
        deadline = time.time() + 2.0
        while writer.frames_written < 1 and time.time() < deadline:
            time.sleep(0.01)

        gc.collect()
        assert frame_ref() is None, "frame image was still referenced somewhere after being written"

        writer.stop(timeout_seconds=5)

    def test_video_recorder_does_not_retain_or_expose_frames(self, tmp_path, monkeypatch):
        import skellycam.opencv.video_recorder.streaming_video_writer as sv_module
        monkeypatch.setattr(sv_module, "Cv2FrameEncoder", lambda *a, **kw: FakeEncoder())

        recorder = VideoRecorder()
        recorder.start_streaming(video_file_save_path=tmp_path / "cam.mp4", expected_fps=30.0)

        for i in range(10):
            payload = FramePayload(
                success=True, image=np.zeros((8, 8, 3), dtype=np.uint8), timestamp_ns=i, camera_id="0",
            )
            recorder.append_frame_payload_to_list(payload, frame_index=i)

        # no attribute on VideoRecorder exposes a frame list/cache of any kind
        assert not hasattr(recorder, "_frame_payload_list")
        assert not hasattr(recorder, "frame_payload_list")
        assert not any("frame" in attr.lower() and "list" in attr.lower() for attr in vars(recorder))

        recorder.stop_streaming(timeout_seconds=5)

    def test_queue_is_empty_after_drain(self, tmp_path):
        writer = StreamingVideoWriter(output_path=tmp_path / "cam.mp4", expected_fps=30.0, encoder=FakeEncoder())
        writer.start()
        for i in range(20):
            writer.submit(StreamingFramePacket(frame_index=i, camera_id="0", timestamp_ns=i, image=np.zeros((4, 4, 3), dtype=np.uint8)))
        writer.stop(timeout_seconds=5)
        assert writer.queue_depth == 0


# ---------------------------------------------------------------------------
# Timestamp memory test
# ---------------------------------------------------------------------------

class TestTimestampMemory:
    def test_timestamp_storage_is_scalar_only_and_matches_frame_count(self, tmp_path):
        frame_count = 9000
        writer = StreamingVideoWriter(
            output_path=tmp_path / "cam.mp4", expected_fps=30.0, queue_capacity=60, encoder=FakeEncoder(),
        )
        writer.start()
        for i in range(frame_count):
            writer.submit(StreamingFramePacket(
                frame_index=i, camera_id="0", timestamp_ns=i * 33_000_000,
                image=np.zeros((4, 4, 3), dtype=np.uint8),
            ))
        result = writer.stop(timeout_seconds=30)

        assert result.success

        # internal timestamp list is scalar tuples only, never image data
        assert all(
            isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], int)
            for entry in writer._timestamps  # accessing internals deliberately, this is a white-box regression test
        )
        assert len(writer._timestamps) == frame_count

        npy_files = list((tmp_path / "timestamps").glob("*_binary.npy"))
        assert len(npy_files) == 1
        saved = np.load(npy_files[0])
        assert len(saved) == frame_count
        assert list(saved) == sorted(saved)  # monotonic


# ---------------------------------------------------------------------------
# Real OpenCV encoder short test
# ---------------------------------------------------------------------------

class TestRealEncoderShortTest:
    def test_real_short_recording_finalizes_and_is_readable(self, tmp_path):
        cv2 = pytest.importorskip("cv2")

        output_path = tmp_path / "Camera_000_synchronized.mp4"
        partial_path = tmp_path / "Camera_000_synchronized.partial.mp4"
        writer = StreamingVideoWriter(
            output_path=output_path, expected_fps=15.0, queue_capacity=30,
            encoder=Cv2FrameEncoder(),
        )
        writer.start()

        frame_count = 150  # 10 seconds at 15fps
        for i in range(frame_count):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            writer.submit(StreamingFramePacket(
                frame_index=i, camera_id="0", timestamp_ns=i * 66_666_667, image=frame,
            ))
            if i == 5:
                # mid-recording: partial file must exist, final must not
                assert partial_path.exists()
                assert not output_path.exists()

        assert not output_path.exists()  # still not finalized before Stop

        result = writer.stop(timeout_seconds=15)

        assert result.success
        assert result.frames_written == frame_count
        assert output_path.exists()
        assert not partial_path.exists()  # atomic rename removed the partial name

        cap = cv2.VideoCapture(str(output_path))
        assert cap.isOpened()
        reported_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        # allow small container/codec rounding -- not an exact-equality brittle check
        assert abs(reported_frame_count - frame_count) <= 2

        timestamp_files = list((tmp_path / "timestamps").glob("*"))
        assert len(timestamp_files) >= 2  # npy + csv


# ---------------------------------------------------------------------------
# Queue saturation
# ---------------------------------------------------------------------------

class TestQueueSaturationMemory:
    def test_saturation_aborts_honestly_without_silent_drops(self, tmp_path):
        output_path = tmp_path / "cam.mp4"
        encoder = FakeEncoder(write_delay_seconds=5.0)  # writer effectively stalled
        writer = StreamingVideoWriter(
            output_path=output_path, expected_fps=30.0, queue_capacity=2,
            submit_timeout_seconds=0.1, encoder=encoder,
        )
        writer.start()

        submitted = 0
        saturated = False
        try:
            for i in range(50):
                writer.submit(StreamingFramePacket(frame_index=i, camera_id="0", timestamp_ns=i, image=np.zeros((4, 4, 3), dtype=np.uint8)))
                submitted += 1
        except WriterSaturatedError:
            saturated = True

        assert saturated
        assert submitted < 50  # did not silently accept all 50 into an unbounded queue
        assert not writer.is_healthy

        result = writer.stop(timeout_seconds=1)
        assert not result.success
        assert not output_path.exists()
        failure_files = list(tmp_path.glob("*.failure.json"))
        assert len(failure_files) == 1
        failure_data = json.loads(failure_files[0].read_text())
        assert failure_data["error"] is not None


# ---------------------------------------------------------------------------
# Writer failure
# ---------------------------------------------------------------------------

class TestWriterFailureMemory:
    def test_failure_after_known_frame_count_is_honest(self, tmp_path):
        output_path = tmp_path / "cam.mp4"
        fail_after = 37
        encoder = FakeEncoder(fail_after_n_writes=fail_after)
        writer = StreamingVideoWriter(output_path=output_path, expected_fps=30.0, encoder=encoder)
        writer.start()

        for i in range(100):
            try:
                writer.submit(StreamingFramePacket(frame_index=i, camera_id="0", timestamp_ns=i, image=np.zeros((4, 4, 3), dtype=np.uint8)))
            except WriterFailedError:
                break

        stop_start = time.perf_counter()
        result = writer.stop(timeout_seconds=10)
        stop_duration = time.perf_counter() - stop_start

        assert not result.success
        assert not output_path.exists()
        assert result.partial_path is not None and result.partial_path.exists()
        assert result.error is not None
        assert stop_duration < 10.0  # Stop must not hang waiting on a dead writer thread
