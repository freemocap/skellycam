"""Tests for framerate tracking, timebase mapping, and timestamp utilities."""
import time

import msgspec
import numpy as np
import pytest

from skellycam.core.recorders.framerate_tracker import (
    CurrentFramerate,
    FramerateTracker,
)
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.utilities.time_unit_conversion import ns_to_ms, ms_to_ns, ns_to_sec, ms_to_sec


# ---------------------------------------------------------------------------
# CurrentFramerate
# ---------------------------------------------------------------------------

class TestCurrentFramerate:
    def test_from_durations_ms(self) -> None:
        durations = np.array([33.33, 33.33, 33.33])
        fr = CurrentFramerate.from_durations_ms(durations_ms=durations, framerate_source="test")
        assert fr.mean_frames_per_second == pytest.approx(30.0, rel=0.01)
        assert fr.mean_frame_duration_ms == pytest.approx(33.33, rel=0.01)
        assert fr.framerate_source == "test"
        assert fr.calculation_window_size == 3

    def test_from_durations_single_frame(self) -> None:
        durations = np.array([16.67])
        fr = CurrentFramerate.from_durations_ms(durations_ms=durations, framerate_source="single")
        assert fr.mean_frames_per_second == pytest.approx(60.0, rel=0.01)

    def test_empty_durations_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            CurrentFramerate.from_durations_ms(
                durations_ms=np.array([]),
                framerate_source="empty",
            )

    def test_zero_mean_raises(self) -> None:
        with pytest.raises(ValueError, match="non-positive"):
            CurrentFramerate.from_durations_ms(
                durations_ms=np.array([0.0, 0.0, 0.0]),
                framerate_source="zero",
            )

    def test_statistics_fields(self) -> None:
        durations = np.array([30.0, 33.0, 36.0, 33.0, 30.0])
        fr = CurrentFramerate.from_durations_ms(durations_ms=durations, framerate_source="stats")
        assert fr.frame_duration_min == pytest.approx(30.0)
        assert fr.frame_duration_max == pytest.approx(36.0)
        assert fr.frame_duration_stddev > 0
        assert fr.frame_duration_coefficient_of_variation > 0

    def test_to_dict(self) -> None:
        durations = np.array([33.0, 34.0])
        fr = CurrentFramerate.from_durations_ms(durations_ms=durations, framerate_source="dict")
        d = msgspec.structs.asdict(fr)
        assert isinstance(d, dict)
        assert "mean_frames_per_second" in d
        assert d["framerate_source"] == "dict"


# ---------------------------------------------------------------------------
# FramerateTracker
# ---------------------------------------------------------------------------

class TestFramerateTracker:
    def test_no_data_initially(self) -> None:
        tracker = FramerateTracker.create(framerate_source="test")
        assert tracker.has_data is False
        with pytest.raises(ValueError, match="No frame durations"):
            _ = tracker.current_framerate

    def test_update_and_read(self) -> None:
        tracker = FramerateTracker.create(framerate_source="test")
        # Simulate 30fps timestamps (33.33ms apart in nanoseconds)
        base = 1_000_000_000
        interval_ns = 33_333_333  # ~30fps
        for i in range(10):
            tracker.update(timestamp_ns=float(base + i * interval_ns))

        assert tracker.has_data is True
        fr = tracker.current_framerate
        assert fr.mean_frames_per_second == pytest.approx(30.0, rel=0.05)

    def test_clear_resets_state(self) -> None:
        tracker = FramerateTracker.create(framerate_source="test")
        tracker.update(timestamp_ns=1_000_000_000.0)
        tracker.update(timestamp_ns=1_033_333_333.0)
        assert tracker.has_data is True

        tracker.clear()
        assert tracker.has_data is False


# ---------------------------------------------------------------------------
# TimebaseMapping
# ---------------------------------------------------------------------------

class TestTimebaseMapping:
    def test_default_creation(self) -> None:
        mapping = TimebaseMapping()
        assert mapping.utc_time_ns > 0
        assert mapping.perf_counter_ns > 0

    def test_perf_to_unix_roundtrip(self) -> None:
        mapping = TimebaseMapping()
        # Converting perf_counter_ns back should give approximately utc_time_ns
        result = mapping.convert_perf_counter_ns_to_unix_ns(
            perf_counter_ns=mapping.perf_counter_ns,
            local_time=False,
        )
        assert result == mapping.utc_time_ns

    def test_perf_to_local_iso8601(self) -> None:
        mapping = TimebaseMapping()
        iso_str = mapping.convert_perf_counter_ns_to_local_iso8601(
            perf_counter_ns=mapping.perf_counter_ns,
        )
        assert isinstance(iso_str, str)
        # Should look like an ISO 8601 string
        assert "T" in iso_str

    def test_numpy_roundtrip(self) -> None:
        original = TimebaseMapping()
        arr = original.to_numpy_record_array()
        assert isinstance(arr, np.recarray)
        restored = TimebaseMapping.from_numpy_record_array(arr)
        assert original == restored

    def test_numpy_wrong_dtype_raises(self) -> None:
        bad_arr = np.recarray((1,), dtype=np.dtype([("garbage", np.int32)]))
        with pytest.raises(ValueError, match="dtype"):
            TimebaseMapping.from_numpy_record_array(bad_arr)

    def test_equality(self) -> None:
        a = TimebaseMapping(utc_time_ns=100, perf_counter_ns=200, local_time_utc_offset=3600)
        b = TimebaseMapping(utc_time_ns=100, perf_counter_ns=200, local_time_utc_offset=3600)
        c = TimebaseMapping(utc_time_ns=999, perf_counter_ns=200, local_time_utc_offset=3600)
        assert a == b
        assert a != c

    def test_hash(self) -> None:
        a = TimebaseMapping(utc_time_ns=100, perf_counter_ns=200, local_time_utc_offset=3600)
        b = TimebaseMapping(utc_time_ns=100, perf_counter_ns=200, local_time_utc_offset=3600)
        assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# FullTimestamp
# ---------------------------------------------------------------------------

class TestFullTimestamp:
    def test_now_creates_valid_timestamp(self) -> None:
        ts = FullTimestamp.now()
        assert ts.unix_timestamp_utc > 0
        assert len(ts.human_friendly_utc) > 0
        assert ts.day_of_week in [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ]
        assert 1 <= ts.calendar_week <= 53
        assert 1 <= ts.day_of_year <= 366

    def test_str_representation(self) -> None:
        ts = FullTimestamp.now()
        s = str(ts)
        assert len(s) > 0
        # Should contain day of week
        assert any(day in s for day in [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ])

    def test_from_timebase_mapping(self) -> None:
        mapping = TimebaseMapping()
        ts = FullTimestamp.from_timebase_mapping(mapping)
        assert ts.unix_timestamp_utc > 0
        assert ts.perf_counter_ns == mapping.perf_counter_ns


# ---------------------------------------------------------------------------
# Time Unit Conversions
# ---------------------------------------------------------------------------

class TestTimeUnitConversion:
    def test_ns_to_ms(self) -> None:
        assert ns_to_ms(1_000_000) == pytest.approx(1.0)
        assert ns_to_ms(0) == pytest.approx(0.0)

    def test_ms_to_ns(self) -> None:
        assert ms_to_ns(1.0) == 1_000_000
        assert ms_to_ns(0.0) == 0

    def test_ns_to_sec(self) -> None:
        assert ns_to_sec(1_000_000_000) == pytest.approx(1.0)

    def test_ms_to_sec(self) -> None:
        assert ms_to_sec(1000.0) == pytest.approx(1.0)

    def test_roundtrip_ns_ms(self) -> None:
        original_ns = 123_456_789
        assert ms_to_ns(ns_to_ms(original_ns)) == original_ns
