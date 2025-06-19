from unittest.mock import MagicMock

import numpy as np
import pytest

from skellycam.core.frame_payloads.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class TestFrameLifespanTimestamps:
    def test_initialization(self):
        """Test that FrameLifespanTimestamps initializes with default values."""
        timebase = TimebaseMapping()
        timestamps = FrameTimestamps(timebase_mapping=timebase)
        
        # Check that frame_initialized_ns is set by default
        assert timestamps.frame_initialized_ns > 0
        
        # Check that other timestamps are initialized to 0
        assert timestamps.pre_frame_grab_ns == 0
        assert timestamps.post_frame_grab_ns == 0
        assert timestamps.pre_frame_retrieve_ns == 0
        assert timestamps.post_frame_retrieve_ns == 0
        assert timestamps.pre_copy_to_camera_shm_ns == 0
        assert timestamps.post_retrieve_from_camera_shm_ns == 0
        assert timestamps.pre_copy_to_multiframe_shm_ns == 0
        assert timestamps.post_retrieve_from_multiframe_shm_ns == 0
        
        # Check that timebase_mapping is set correctly
        assert timestamps.timebase_mapping == timebase

    def test_timestamp_local_unix_ns_property(self):
        """Test the timestamp_local_unix_ns computed property."""
        # Create a mock TimebaseMapping to control the conversion
        mock_timebase = MagicMock(spec=TimebaseMapping)
        mock_timebase.convert_perf_counter_ns_to_unix_ns.return_value = 1000
        
        timestamps = FrameTimestamps(
            timebase_mapping=mock_timebase,
            pre_frame_grab_ns=1000,
            post_frame_grab_ns=3000
        )
        
        # Should use the midpoint between pre and post grab
        expected_midpoint = (3000 - 1000) // 2
        _ = timestamps.timestamp_local_unix_ms
        
        # Verify the conversion was called with the correct midpoint
        mock_timebase.convert_perf_counter_ns_to_unix_ns.assert_called_once_with(expected_midpoint, local_time=True)
        
        # Test error case
        timestamps.pre_frame_grab_ns = None
        with pytest.raises(ValueError):
            _ = timestamps.timestamp_local_unix_ms

    def test_local_unix_ms_conversions(self):
        """Test the local_unix_ms computed properties."""
        # Create a mock TimebaseMapping to control the conversion
        mock_timebase = MagicMock(spec=TimebaseMapping)
        mock_timebase.convert_perf_counter_ns_to_unix_ns.return_value = 1_000_000_000  # 1 second in ns
        
        timestamps = FrameTimestamps(
            timebase_mapping=mock_timebase,
            frame_initialized_ns=1000,
            pre_frame_grab_ns=2000,
            post_frame_grab_ns=3000,
            pre_frame_retrieve_ns=4000,
            post_frame_retrieve_ns=5000,
            pre_copy_to_camera_shm_ns=6000,
            post_retrieve_from_camera_shm_ns=7000,
            pre_copy_to_multiframe_shm_ns=8000,
            post_retrieve_from_multiframe_shm_ns=9000
        )
        
        # Test that all the ms conversions work correctly
        assert timestamps.frame_initialized_local_unix_ms == 1000  # 1_000_000_000 // 1_000_000
        assert timestamps.pre_grab_local_unix_ms == 1000
        assert timestamps.post_grab_local_unix_ms == 1000
        assert timestamps.pre_retrieve_local_unix_ms == 1000
        assert timestamps.post_retrieve_local_unix_ms == 1000
        assert timestamps.copy_to_camera_shm_local_unix_ms == 1000
        assert timestamps.retrieve_from_camera_shm_local_unix_ms == 1000
        assert timestamps.copy_to_multiframe_shm_local_unix_ms == 1000
        assert timestamps.retrieve_from_multiframe_shm_local_unix_ms == 1000

    def test_timing_metrics(self):
        """Test the computed timing metrics."""
        timebase = TimebaseMapping()
        
        # Create timestamps with sequential values for easy testing
        timestamps = FrameTimestamps(
            timebase_mapping=timebase,
            frame_initialized_ns=1000,
            pre_frame_grab_ns=2000,
            post_frame_grab_ns=3000,
            pre_frame_retrieve_ns=4000,
            post_frame_retrieve_ns=5000,
            pre_copy_to_camera_shm_ns=6000,
            post_retrieve_from_camera_shm_ns=7000,
            pre_copy_to_multiframe_shm_ns=8000,
            post_retrieve_from_multiframe_shm_ns=9000
        )
        
        # Test individual timing metrics
        assert timestamps.idle_before_grab_duration_ms == .001  # 2000 - 1000
        assert timestamps.frame_grab_duration_ms == .001  # 3000 - 2000
        assert timestamps.idle_before_retrieve_duration_ms == .001  # 4000 - 3000
        assert timestamps.frame_retrieve_duration_ms == .001  # 5000 - 4000
        assert timestamps.idle_before_copy_to_camera_shm_duration_ms == .001  # 6000 - 5000
        assert timestamps.idle_in_camera_shm_duration_ms == .001  # 7000 - 6000
        assert timestamps.idle_before_copy_to_multiframe_shm_duration_ms == .001  # 8000 - 7000
        assert timestamps.idle_in_multiframe_shm_duration_ms == .001  # 9000 - 8000
        
        # Test higher-level category timing metrics
        assert timestamps.total_frame_acquisition_duration_ms == .003  # 5000 - 2000
        assert timestamps.total_ipc_travel_duration_ms == .004  # 9000 - 5000

    def test_numpy_conversion(self):
        """Test conversion to and from numpy record arrays."""
        timebase = TimebaseMapping()
        original = FrameTimestamps(
            timebase_mapping=timebase,
            frame_initialized_ns=1000,
            pre_frame_grab_ns=2000,
            post_frame_grab_ns=3000,
            pre_frame_retrieve_ns=4000,
            post_frame_retrieve_ns=5000,
            pre_copy_to_camera_shm_ns=6000,
            post_retrieve_from_camera_shm_ns=7000,
            pre_copy_to_multiframe_shm_ns=8000,
            post_retrieve_from_multiframe_shm_ns=9000
        )
        
        # Convert to numpy record array
        record_array = original.to_numpy_record_array()
        
        # Check the record array properties
        assert isinstance(record_array, np.recarray)
        assert record_array.shape == (1,)
        assert record_array.dtype == FRAME_LIFECYCLE_TIMESTAMPS_DTYPE
        
        # Check values in the record array
        assert record_array.frame_initialized_ns[0] == 1000
        assert record_array.pre_frame_grab_ns[0] == 2000
        assert record_array.post_frame_grab_ns[0] == 3000
        assert record_array.pre_frame_retrieve_ns[0] == 4000
        assert record_array.post_frame_retrieve_ns[0] == 5000
        assert record_array.copy_to_camera_shm_ns[0] == 6000
        assert record_array.retrieve_from_camera_shm_ns[0] == 7000
        assert record_array.copy_to_multiframe_shm_ns[0] == 8000
        assert record_array.retrieve_from_multiframe_shm_ns[0] == 9000
        
        # Convert back to FrameLifespanTimestamps
        reconstructed = FrameTimestamps.from_numpy_record_array(record_array)
        
        # Check that the reconstructed object has the same values
        assert reconstructed.frame_initialized_ns == original.frame_initialized_ns
        assert reconstructed.pre_frame_grab_ns == original.pre_frame_grab_ns
        assert reconstructed.post_frame_grab_ns == original.post_frame_grab_ns
        assert reconstructed.pre_frame_retrieve_ns == original.pre_frame_retrieve_ns
        assert reconstructed.post_frame_retrieve_ns == original.post_frame_retrieve_ns
        assert reconstructed.pre_copy_to_camera_shm_ns == original.pre_copy_to_camera_shm_ns
        assert reconstructed.post_retrieve_from_camera_shm_ns == original.post_retrieve_from_camera_shm_ns
        assert reconstructed.pre_copy_to_multiframe_shm_ns == original.pre_copy_to_multiframe_shm_ns
        assert reconstructed.post_retrieve_from_multiframe_shm_ns == original.post_retrieve_from_multiframe_shm_ns
        
        # Check that timebase mapping was also reconstructed correctly
        assert reconstructed.timebase_mapping.utc_time_ns == original.timebase_mapping.utc_time_ns
        assert reconstructed.timebase_mapping.perf_counter_ns == original.timebase_mapping.perf_counter_ns
        assert reconstructed.timebase_mapping.local_time_utc_offset == original.timebase_mapping.local_time_utc_offset

    def test_from_numpy_record_array_validation(self):
        """Test validation when creating from numpy record array with wrong dtype."""
        # Create a record array with incorrect dtype
        wrong_dtype = np.dtype([('wrong_field', np.int32)])
        wrong_array = np.recarray(1, dtype=wrong_dtype)
        
        # Should raise ValueError
        with pytest.raises(ValueError):
            FrameTimestamps.from_numpy_record_array(wrong_array)

    def test_negative_timing_metrics_for_unset_values(self):
        """Test that timing metrics return -1 when timestamps are not set."""
        timebase = TimebaseMapping()
        timestamps = FrameTimestamps(timebase_mapping=timebase)
        
        # All metrics should return -1 since no timestamps are set (except frame_initialized_ns)
        assert timestamps.idle_before_grab_duration_ms == -1
        assert timestamps.frame_grab_duration_ms == -1
        assert timestamps.idle_before_retrieve_duration_ms == -1
        assert timestamps.frame_retrieve_duration_ms == -1
        assert timestamps.idle_before_copy_to_camera_shm_duration_ms == -1
        assert timestamps.idle_in_camera_shm_duration_ms == -1
        assert timestamps.idle_before_copy_to_multiframe_shm_duration_ms == -1
        assert timestamps.idle_in_multiframe_shm_duration_ms == -1
        assert timestamps.total_frame_acquisition_duration_ms == -1
        assert timestamps.total_ipc_travel_duration_ms == -1