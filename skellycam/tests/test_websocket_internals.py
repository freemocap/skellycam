"""Tests for WebSocket server-side framerate calculation and performance data extraction."""
import numpy as np
import pytest

from skellycam.api.websocket.websocket_server import ServerFramerateCalculator
from skellycam.api.websocket.performance_data import (
    extract_performance_data_from_frames,
    _ns_to_ms,
    _safe_duration_ms,
)
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.types.frame_dtype_factories import create_frame_dtype


# ---------------------------------------------------------------------------
# ServerFramerateCalculator
# ---------------------------------------------------------------------------

class TestServerFramerateCalculator:
    def test_no_data_returns_none(self) -> None:
        calc = ServerFramerateCalculator(source_name="test")
        assert calc.current_framerate is None

    def test_single_observation_returns_none(self) -> None:
        calc = ServerFramerateCalculator(source_name="test")
        calc.update(frame_number=0, capture_timestamp_ns=1_000_000_000.0)
        assert calc.current_framerate is None

    def test_consecutive_frames_compute_framerate(self) -> None:
        calc = ServerFramerateCalculator(source_name="test")
        base_ns = 1_000_000_000.0
        interval_ns = 33_333_333.0  # ~30fps

        for i in range(10):
            calc.update(
                frame_number=i,
                capture_timestamp_ns=base_ns + i * interval_ns,
            )

        fr = calc.current_framerate
        assert fr is not None
        assert fr.mean_frames_per_second == pytest.approx(30.0, rel=0.05)
        assert fr.framerate_source == "test"

    def test_skipped_frames_compute_true_rate(self) -> None:
        """When frames are skipped (backpressure), the calculator should still
        compute the true per-frame capture rate, not the websocket send rate."""
        calc = ServerFramerateCalculator(source_name="test")
        base_ns = 1_000_000_000.0
        interval_ns = 33_333_333.0  # ~30fps

        # Send every other frame (simulating backpressure skip)
        for i in range(0, 20, 2):
            calc.update(
                frame_number=i,
                capture_timestamp_ns=base_ns + i * interval_ns,
            )

        fr = calc.current_framerate
        assert fr is not None
        # Should still be ~30fps (true capture rate), not 15fps (display rate)
        assert fr.mean_frames_per_second == pytest.approx(30.0, rel=0.1)

    def test_clear_resets(self) -> None:
        calc = ServerFramerateCalculator(source_name="test")
        base_ns = 1_000_000_000.0
        interval_ns = 33_333_333.0
        for i in range(5):
            calc.update(frame_number=i, capture_timestamp_ns=base_ns + i * interval_ns)
        assert calc.current_framerate is not None

        calc.clear()
        assert calc.current_framerate is None


# ---------------------------------------------------------------------------
# Performance Data Extraction helpers
# ---------------------------------------------------------------------------

class TestPerformanceDataHelpers:
    def test_ns_to_ms(self) -> None:
        assert _ns_to_ms(1_000_000) == pytest.approx(1.0)
        assert _ns_to_ms(0) == pytest.approx(0.0)

    def test_safe_duration_ms(self) -> None:
        assert _safe_duration_ms(1_000_000, 2_000_000) == pytest.approx(1.0)
        assert _safe_duration_ms(0, 0) == -1.0


# ---------------------------------------------------------------------------
# Performance Data Extraction
# ---------------------------------------------------------------------------

class TestExtractPerformanceData:
    @staticmethod
    def _make_fake_frame(
        camera_id: str,
        camera_index: int,
        frame_number: int,
        base_ts_ns: int,
    ) -> np.recarray:
        config = CameraConfig(
            camera_id=camera_id,
            camera_index=camera_index,
            resolution=ImageResolution(height=48, width=64),
        )
        frame_dtype = create_frame_dtype(config)
        frame = np.recarray(1, dtype=frame_dtype)
        frame.frame_metadata.camera_info[0] = config.to_frame_camera_info()
        frame.frame_metadata.frame_number[0] = frame_number

        ts = frame.frame_metadata.timestamps
        ts.initialized_ns[0] = base_ts_ns
        ts.pre_frame_grab_ns[0] = base_ts_ns + 1_000_000
        ts.post_frame_grab_ns[0] = base_ts_ns + 2_000_000
        ts.pre_frame_retrieve_ns[0] = base_ts_ns + 3_000_000
        ts.post_frame_retrieve_ns[0] = base_ts_ns + 10_000_000
        ts.pre_copy_to_camera_shm_ns[0] = base_ts_ns + 11_000_000
        ts.post_copy_to_camera_shm_ns[0] = base_ts_ns + 12_000_000
        ts.pre_frame_record_ns[0] = base_ts_ns + 13_000_000
        ts.post_frame_record_ns[0] = base_ts_ns + 14_000_000

        frame.image[0] = np.zeros((48, 64, 3), dtype=np.uint8)
        return frame

    def test_single_camera(self) -> None:
        frame = self._make_fake_frame("cam0", 0, frame_number=5, base_ts_ns=100_000_000)
        session_start = 0

        result = extract_performance_data_from_frames(
            latest_frames={"cam0": frame},
            session_start_perf_ns=session_start,
        )

        assert result["message_type"] == "performance_data"
        assert result["frame_number"] == 5
        assert len(result["camera_lifecycle_rows"]) == 1

        row = result["camera_lifecycle_rows"][0]
        assert row["camera_id"] == "cam0"
        assert row["frame_number"] == 5
        assert row["grab_duration_ms"] > 0
        assert row["retrieve_duration_ms"] > 0

        sync = result["inter_camera_sync"]
        assert sync["num_cameras"] == 1
        assert sync["grab_range_ms"] == pytest.approx(0.0)

    def test_multi_camera_sync_metrics(self) -> None:
        # Two cameras with slightly different grab timestamps
        frame0 = self._make_fake_frame("cam0", 0, frame_number=10, base_ts_ns=100_000_000)
        frame1 = self._make_fake_frame("cam1", 1, frame_number=10, base_ts_ns=100_500_000)

        result = extract_performance_data_from_frames(
            latest_frames={"cam0": frame0, "cam1": frame1},
            session_start_perf_ns=0,
        )

        assert result["inter_camera_sync"]["num_cameras"] == 2
        assert result["inter_camera_sync"]["grab_range_ms"] > 0
        assert len(result["camera_lifecycle_rows"]) == 2

    def test_empty_frames_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            extract_performance_data_from_frames(
                latest_frames={},
                session_start_perf_ns=0,
            )
