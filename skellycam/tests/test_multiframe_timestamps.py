import pytest
from unittest.mock import MagicMock, patch

import numpy as np

from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.frame_payloads.multiframe_timestamps import MultiframeTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.sample_statistics import DescriptiveStatistics


class TestMultiframeTimestamps:
    def setup_method(self):
        """Set up test fixtures for each test method."""
        # Create a timebase mapping for use in tests
        self.timebase = TimebaseMapping()
        
        # Create sample frame timestamps for multiple cameras
        self.camera1_timestamps = FrameLifespanTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=1000,
            pre_grab_ns=2000,
            post_grab_ns=3000,
            pre_retrieve_ns=4000,
            post_retrieve_ns=5000,
            copy_to_camera_shm_ns=6000,
            retrieve_from_camera_shm_ns=7000,
            copy_to_multiframe_shm_ns=8000,
            retrieve_from_multiframe_shm_ns=9000
        )
        
        self.camera2_timestamps = FrameLifespanTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=1500,
            pre_grab_ns=2500,
            post_grab_ns=3500,
            pre_retrieve_ns=4500,
            post_retrieve_ns=5500,
            copy_to_camera_shm_ns=6500,
            retrieve_from_camera_shm_ns=7500,
            copy_to_multiframe_shm_ns=8500,
            retrieve_from_multiframe_shm_ns=9500
        )
        
        # Create a dictionary of frame timestamps
        self.frame_timestamps = {
            "camera1": self.camera1_timestamps,
            "camera2": self.camera2_timestamps
        }
        
        # Create a MultiframeTimestamps instance
        self.multiframe_timestamps = MultiframeTimestamps(
            frame_timestamps=self.frame_timestamps,
            principal_camera_id="camera1"
        )

    def test_initialization(self):
        """Test that MultiframeTimestamps initializes correctly."""
        assert self.multiframe_timestamps.frame_timestamps == self.frame_timestamps
        assert self.multiframe_timestamps.principal_camera_id == "camera1"
        
        # Check that the frame_timestamps dictionary contains the expected keys
        assert set(self.multiframe_timestamps.frame_timestamps.keys()) == {"camera1", "camera2"}
        
        # Check that the frame_timestamps dictionary contains FrameLifespanTimestamps objects
        for ts in self.multiframe_timestamps.frame_timestamps.values():
            assert isinstance(ts, FrameLifespanTimestamps)

    def test_from_multiframe(self):
        """Test creating MultiframeTimestamps from a MultiFramePayload."""
        # Create a mock MultiFramePayload
        mock_multiframe = MagicMock()
        mock_multiframe.frames = {
            "camera1": MagicMock(timestamps=self.camera1_timestamps),
            "camera2": MagicMock(timestamps=self.camera2_timestamps)
        }
        mock_multiframe.principal_camera_id = "camera1"
        
        # Create MultiframeTimestamps from the mock MultiFramePayload
        multiframe_timestamps = MultiframeTimestamps.from_multiframe(mock_multiframe)
        
        # Check that the MultiframeTimestamps was created correctly
        assert multiframe_timestamps.frame_timestamps == self.frame_timestamps
        assert multiframe_timestamps.principal_camera_id == "camera1"

    def test_timestamps_local_unix_ms_property(self):
        """Test the timestamps_local_unix_ms computed property."""
        # Mock the timestamp_local_unix_ms property of FrameLifespanTimestamps
        with patch.object(FrameLifespanTimestamps, 'timestamp_local_unix_ms', 
                          new_callable=lambda: 1000, create=True):
            timestamps_dict = self.multiframe_timestamps.timestamps_local_unix_ms
            
            # Check that the dictionary contains the expected keys
            assert set(timestamps_dict.keys()) == {"camera1", "camera2"}
            
            # Check that the values are correct
            assert timestamps_dict["camera1"] == 1000
            assert timestamps_dict["camera2"] == 1000

    def test_descriptive_statistics_properties(self):
        """Test that all descriptive statistics properties return DescriptiveStatistics objects."""
        # List of all descriptive statistics properties
        stat_properties = [
            "timestamp_local_unix_ms",
            "frame_initialized_local_unix_ms",
            "pre_grab_local_unix_ms",
            "post_grab_local_unix_ms",
            "pre_retrieve_local_unix_ms",
            "post_retrieve_local_unix_ms",
            "copy_to_camera_shm_local_unix_ms",
            "retrieve_from_camera_shm_local_unix_ms",
            "copy_to_multiframe_shm_local_unix_ms",
            "retrieve_from_multiframe_shm_local_unix_ms",
            "idle_before_grab_duration_ms",
            "frame_grab_duration_ms",
            "idle_before_retrieve_duration_ms",
            "frame_retrieve_duration_ms",
            "idle_before_copy_to_camera_shm_duration_ms",
            "idle_in_camera_shm_duration_duration_ms",
            "idle_before_copy_to_multiframe_shm_duration_ms",
            "idle_in_multiframe_shm_duration_ms",
            "total_frame_acquisition_duration_ms",
            "total_ipc_travel_duration_ms"
        ]
        
        # Mock DescriptiveStatistics.from_samples to return a mock object
        mock_stats = MagicMock(spec=DescriptiveStatistics)
        with patch('skellycam.utilities.sample_statistics.DescriptiveStatistics.from_samples', 
                   return_value=mock_stats):
            
            # Check that each property returns a DescriptiveStatistics object
            for prop_name in stat_properties:
                prop_value = getattr(self.multiframe_timestamps, prop_name)
                assert prop_value == mock_stats

    def test_statistics_calculation(self):
        """Test that statistics are calculated correctly from frame timestamps."""
        # Test a few representative properties to verify statistics calculation
        
        # For idle_before_grab_duration_ms, we expect values of 0.001 ms for both cameras
        # The DescriptiveStatistics should have mean=0.001, min=0.001, max=0.001, etc.
        idle_stats = self.multiframe_timestamps.idle_before_grab_duration_ms
        assert isinstance(idle_stats, DescriptiveStatistics)
        assert idle_stats.mean == pytest.approx(0.001)
        assert idle_stats.min == pytest.approx(0.001)
        assert idle_stats.max == pytest.approx(0.001)
        assert idle_stats.name == "idle_before_grab_duration_ms"
        assert idle_stats.units == "milliseconds"
        
        # For frame_grab_duration_ms, we expect values of 0.001 ms for both cameras
        grab_stats = self.multiframe_timestamps.frame_grab_duration_ms
        assert isinstance(grab_stats, DescriptiveStatistics)
        assert grab_stats.mean == pytest.approx(0.001)
        assert grab_stats.min == pytest.approx(0.001)
        assert grab_stats.max == pytest.approx(0.001)
        assert grab_stats.name == "frame_grab_duration_ms"
        assert grab_stats.units == "milliseconds"
        
        # For total_frame_acquisition_duration_ms, we expect values of 0.003 ms for both cameras
        acquisition_stats = self.multiframe_timestamps.total_frame_acquisition_duration_ms
        assert isinstance(acquisition_stats, DescriptiveStatistics)
        assert acquisition_stats.mean == pytest.approx(0.003)
        assert acquisition_stats.min == pytest.approx(0.003)
        assert acquisition_stats.max == pytest.approx(0.003)
        assert acquisition_stats.name == "total_frame_acquisition_duration_ms"
        assert acquisition_stats.units == "milliseconds"

    def test_with_empty_frame_timestamps(self):
        """Test behavior with an empty frame_timestamps dictionary."""
        empty_multiframe = MultiframeTimestamps(
            frame_timestamps={},
            principal_camera_id="camera1"
        )
        
        # When frame_timestamps is empty, accessing descriptive statistics properties
        # should raise a ValueError because there are no samples to compute statistics from
        with pytest.raises(ValueError, match="Sample list must have at least 1 sample"):
            _ = empty_multiframe.idle_before_grab_duration_ms
