import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from skellycam.core.timestamps.frame_timestamps import FrameTimestamps, FrameDurations
from skellycam.core.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics
from skellycam.utilities.time_unit_conversion import ns_to_ms


class TestMultiframeTimestamps:
    def setup_method(self):
        """Set up test fixtures for each test method."""
        # Create a timebase mapping for use in tests
        self.timebase = TimebaseMapping()

        # Create sample frame timestamps for multiple cameras with controlled values
        base_time = 1_000_000_000  # 1 second in ns

        # Camera 1 timestamps
        self.camera1_timestamps = FrameTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=base_time,
            pre_frame_grab_ns=base_time + 100_000_000,  # +100ms
            post_frame_grab_ns=base_time + 300_000_000,  # +300ms (+200ms from previous)
            pre_frame_retrieve_ns=base_time + 400_000_000,  # +400ms (+100ms from previous)
            post_frame_retrieve_ns=base_time + 600_000_000,  # +600ms (+200ms from previous)
            pre_copy_to_camera_shm_ns=base_time + 700_000_000,  # +700ms (+100ms from previous)
            pre_retrieve_from_camera_shm_ns=base_time + 800_000_000,  # +800ms (+100ms from previous)
            post_retrieve_from_camera_shm_ns=base_time + 900_000_000,  # +900ms (+100ms from previous)
            pre_copy_to_multiframe_shm_ns=base_time + 1_000_000_000,  # +1000ms (+100ms from previous)
            pre_retrieve_from_multiframe_shm_ns=base_time + 1_100_000_000,  # +1100ms (+100ms from previous)
            post_retrieve_from_multiframe_shm_ns=base_time + 1_200_000_000,  # +1200ms (+100ms from previous)
        )

        # Camera 2 timestamps (slightly different timing)
        self.camera2_timestamps = FrameTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=base_time + 50_000_000,  # +50ms from base
            pre_frame_grab_ns=base_time + 150_000_000,  # +150ms (+100ms from initialized)
            post_frame_grab_ns=base_time + 350_000_000,  # +350ms (+200ms from pre_grab)
            pre_frame_retrieve_ns=base_time + 450_000_000,  # +450ms (+100ms from post_grab)
            post_frame_retrieve_ns=base_time + 650_000_000,  # +650ms (+200ms from pre_retrieve)
            pre_copy_to_camera_shm_ns=base_time + 750_000_000,  # +750ms (+100ms from post_retrieve)
            pre_retrieve_from_camera_shm_ns=base_time + 850_000_000,  # +850ms (+100ms from pre_copy)
            post_retrieve_from_camera_shm_ns=base_time + 950_000_000,  # +950ms (+100ms from pre_retrieve)
            pre_copy_to_multiframe_shm_ns=base_time + 1_050_000_000,  # +1050ms (+100ms from post_retrieve)
            pre_retrieve_from_multiframe_shm_ns=base_time + 1_150_000_000,  # +1150ms (+100ms from pre_copy)
            post_retrieve_from_multiframe_shm_ns=base_time + 1_250_000_000,  # +1250ms (+100ms from pre_retrieve)
        )

        # Create a dictionary of frame timestamps
        self.frame_timestamps = {
            "camera1": self.camera1_timestamps,
            "camera2": self.camera2_timestamps
        }

        # Recording start time (for relative timing)
        self.recording_start_time_ns = base_time - 500_000_000  # 500ms before base time

        # Create a MultiframeTimestamps instance
        self.multiframe_timestamps = MultiFrameTimestamps(
            frame_timestamps=self.frame_timestamps,
            recording_start_time_ns=self.recording_start_time_ns,
            multiframe_number=1
        )

    def test_initialization(self):
        """Test that MultiframeTimestamps initializes correctly."""
        assert self.multiframe_timestamps.frame_timestamps == self.frame_timestamps
        assert self.multiframe_timestamps.recording_start_time_ns == self.recording_start_time_ns
        assert self.multiframe_timestamps.multiframe_number == 1

        # Check that the frame_timestamps dictionary contains the expected keys
        assert set(self.multiframe_timestamps.frame_timestamps.keys()) == {"camera1", "camera2"}

        # Check that the frame_timestamps dictionary contains FrameTimestamps objects
        for ts in self.multiframe_timestamps.frame_timestamps.values():
            assert isinstance(ts, FrameTimestamps)

    def test_from_multiframe(self):
        """Test creating MultiframeTimestamps from a MultiFramePayload."""
        # Create a mock MultiFramePayload
        mock_multiframe = MagicMock()
        mock_multiframe.frames = {
            "camera1": MagicMock(frame_metadata=MagicMock(timestamps=self.camera1_timestamps)),
            "camera2": MagicMock(frame_metadata=MagicMock(timestamps=self.camera2_timestamps))
        }
        mock_multiframe.multi_frame_number = 1

        # Create MultiframeTimestamps from the mock MultiFramePayload
        multiframe_timestamps = MultiFrameTimestamps.from_multiframe(
            mock_multiframe,
            recording_start_time_ns=self.recording_start_time_ns
        )

        # Check that the MultiframeTimestamps was created correctly
        assert multiframe_timestamps.frame_timestamps == self.frame_timestamps
        assert multiframe_timestamps.recording_start_time_ns == self.recording_start_time_ns
        assert multiframe_timestamps.multiframe_number == 1

    def test_timestamps_ns_property(self):
        """Test the timestamps_ns property."""
        timestamps_dict = self.multiframe_timestamps.timestamps_ns

        # Check that the dictionary contains the expected keys
        assert set(timestamps_dict.keys()) == {"camera1", "camera2"}

        # Check that the values are correct (should be the midpoint of pre and post grab)
        # For camera1: pre_grab = base + 100ms, post_grab = base + 300ms, so timestamp = base + 200ms
        # For camera2: pre_grab = base + 150ms, post_grab = base + 350ms, so timestamp = base + 250ms
        base_time = 1_000_000_000
        assert timestamps_dict["camera1"] == base_time + 200_000_000  # Midpoint between pre and post grab
        assert timestamps_dict["camera2"] == base_time + 250_000_000  # Midpoint between pre and post grab

    def test_timestamp_ns_statistics(self):
        """Test the timestamp_ns statistics property."""
        stats = self.multiframe_timestamps.timestamp_ns

        assert isinstance(stats, DescriptiveStatistics)
        assert stats.name == "timestamp_ns"
        assert stats.units == "nanoseconds"

        # Check statistics calculations
        base_time = 1_000_000_000
        # Midpoints between pre and post grab for each camera
        values = [base_time + 200_000_000, base_time + 250_000_000]
        assert stats.mean == sum(values) / len(values)
        assert stats.min == min(values)
        assert stats.max == max(values)
        assert stats.range == max(values) - min(values)
        assert stats.number_of_samples == 2

    def test_inter_camera_grab_range_ms(self):
        """Test the inter_camera_grab_range_ms property."""
        # The range should be the difference between camera timestamps in ms
        # Camera1: base + 200ms, Camera2: base + 250ms, so range = 50ms
        range_ms = self.multiframe_timestamps.inter_camera_grab_range_ms
        assert range_ms == 50.0

    def test_timestamp_statistics_properties(self):
        """Test all timestamp statistics properties."""
        # Test a few representative timestamp properties

        # frame_initialized_ms
        init_stats = self.multiframe_timestamps.frame_initialized_ms
        assert isinstance(init_stats, DescriptiveStatistics)
        assert init_stats.name == "frame_initialized_ms"
        assert init_stats.units == "milliseconds"

        base_time_ms = 1_000_000_000 / 1_000_000  # 1000ms
        values = [base_time_ms, base_time_ms + 50]  # 1000ms, 1050ms
        assert init_stats.mean == sum(values) / len(values)
        assert init_stats.min == min(values)
        assert init_stats.max == max(values)

        # pre_grab_ms
        pre_grab_stats = self.multiframe_timestamps.pre_grab_ms
        assert isinstance(pre_grab_stats, DescriptiveStatistics)
        values = [base_time_ms + 100, base_time_ms + 150]  # 1100ms, 1150ms
        assert pre_grab_stats.mean == sum(values) / len(values)
        assert pre_grab_stats.min == min(values)
        assert pre_grab_stats.max == max(values)

        # post_grab_ms
        post_grab_stats = self.multiframe_timestamps.post_grab_ms
        assert isinstance(post_grab_stats, DescriptiveStatistics)
        values = [base_time_ms + 300, base_time_ms + 350]  # 1300ms, 1350ms
        assert post_grab_stats.mean == sum(values) / len(values)
        assert post_grab_stats.min == min(values)
        assert post_grab_stats.max == max(values)

    def test_duration_statistics_properties(self):
        """Test all duration statistics properties."""
        # Test a few representative duration properties

        # idle_before_grab_ms
        idle_before_grab_stats = self.multiframe_timestamps.idle_before_grab_ms
        assert isinstance(idle_before_grab_stats, DescriptiveStatistics)
        assert idle_before_grab_stats.name == "idle_before_grab_ms"
        assert idle_before_grab_stats.units == "milliseconds"

        # Both cameras have 100ms idle before grab
        assert idle_before_grab_stats.mean == 100
        assert idle_before_grab_stats.min == 100
        assert idle_before_grab_stats.max == 100

        # during_frame_grab_ms
        during_frame_grab_stats = self.multiframe_timestamps.during_frame_grab_ms
        assert isinstance(during_frame_grab_stats, DescriptiveStatistics)

        # Both cameras have 200ms during frame grab
        assert during_frame_grab_stats.mean == 200
        assert during_frame_grab_stats.min == 200
        assert during_frame_grab_stats.max == 200

        # total_frame_acquisition_time_ms
        total_acquisition_stats = self.multiframe_timestamps.total_frame_acquisition_time_ms
        assert isinstance(total_acquisition_stats, DescriptiveStatistics)

        # Both cameras have 500ms total acquisition time (post_retrieve - pre_grab)
        assert total_acquisition_stats.mean == 500
        assert total_acquisition_stats.min == 500
        assert total_acquisition_stats.max == 500

    def test_all_duration_calculations(self):
        """Test all duration calculations to ensure they match expected values."""
        # Define expected values for all durations in milliseconds
        expected_durations = {
            "idle_before_grab_ms": 100,
            "during_frame_grab_ms": 200,
            "idle_before_retrieve_ms": 100,
            "during_frame_retrieve_ms": 200,
            "idle_before_copy_to_camera_shm_ms": 100,
            "stored_in_camera_shm_ms": 200,  # from pre_copy to post_retrieve
            "during_copy_from_camera_shm_ms": 100,  # from pre_retrieve to post_retrieve
            "idle_before_copy_to_multiframe_shm_ms": 100,
            "stored_in_multiframe_shm_ms": 200,  # from pre_copy to post_retrieve
            "during_copy_from_multiframe_shm_ms": 100,  # from pre_retrieve to post_retrieve
            "total_frame_acquisition_time_ms": 500,  # from pre_grab to post_retrieve
            "total_ipc_travel_time_ms": 600,  # from post_retrieve to post_retrieve_from_multiframe_shm
        }

        # Check each duration property
        for duration_name, expected_value in expected_durations.items():
            stats = getattr(self.multiframe_timestamps, duration_name)
            assert isinstance(stats, DescriptiveStatistics)
            assert stats.mean == expected_value, f"Expected {duration_name} to be {expected_value}ms, got {stats.mean}ms"
            assert stats.min == expected_value
            assert stats.max == expected_value

    def test_with_empty_frame_timestamps(self):
        """Test behavior with an empty frame_timestamps dictionary."""
        empty_multiframe = MultiFrameTimestamps(
            frame_timestamps={},
            recording_start_time_ns=self.recording_start_time_ns,
            multiframe_number=1
        )

        # When frame_timestamps is empty, accessing descriptive statistics properties
        # should raise a ValueError because there are no samples to compute statistics from
        with pytest.raises(ValueError, match="Sample list must have at least 1 sample"):
            _ = empty_multiframe.idle_before_grab_ms