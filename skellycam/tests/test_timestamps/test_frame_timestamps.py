

import numpy as np
import pytest

from skellycam.core.timestamps.frame_timestamps import FrameTimestamps, FrameDurations
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE


class TestFrameTimestamps:
    def test_initialization(self):
        """Test that FrameTimestamps initializes with default values."""
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
        assert timestamps.pre_retrieve_from_camera_shm_ns == 0
        assert timestamps.post_retrieve_from_camera_shm_ns == 0
        assert timestamps.pre_copy_to_multiframe_shm_ns == 0
        assert timestamps.pre_retrieve_from_multiframe_shm_ns == 0
        assert timestamps.post_retrieve_from_multiframe_shm_ns == 0

        # Check that timebase_mapping is set correctly
        assert timestamps.timebase_mapping == timebase

    def test_timestamp_property(self):
        """Test the timestamp_ns property."""
        timebase = TimebaseMapping()

        timestamps = FrameTimestamps(
            timebase_mapping=timebase,
            pre_frame_grab_ns=1000,
            post_frame_grab_ns=3000
        )

        # Should use the midpoint between pre and post grab
        assert timestamps.timestamp_ns == 2000  # (3000 + 1000) // 2

        # Test error case
        timestamps = FrameTimestamps(timebase_mapping=timebase)
        with pytest.raises(ValueError):
            _ = timestamps.timestamp_ns

    def test_durations_property(self):
        """Test the durations property."""
        timebase = TimebaseMapping()

        timestamps = FrameTimestamps(
            timebase_mapping=timebase,
            frame_initialized_ns=1000,
            pre_frame_grab_ns=2000,
            post_frame_grab_ns=3000,
            pre_frame_retrieve_ns=4000,
            post_frame_retrieve_ns=5000,
            pre_copy_to_camera_shm_ns=6000,
            pre_retrieve_from_camera_shm_ns=7000,
            post_retrieve_from_camera_shm_ns=8000,
            pre_copy_to_multiframe_shm_ns=9000,
            pre_retrieve_from_multiframe_shm_ns=10000,
            post_retrieve_from_multiframe_shm_ns=11000
        )

        durations = timestamps.durations
        assert isinstance(durations, FrameDurations)

        # Test that durations are calculated correctly
        assert durations.idle_before_grab_ns == 1000  # 2000 - 1000
        assert durations.during_frame_grab_ns == 1000  # 3000 - 2000
        assert durations.idle_before_retrieve_ns == 1000  # 4000 - 3000
        assert durations.during_frame_retrieve_ns == 1000  # 5000 - 4000
        assert durations.idle_before_copy_to_camera_shm_ns == 1000  # 6000 - 5000
        assert durations.stored_in_camera_shm_ns == 2000  # 8000 - 6000
        assert durations.during_copy_from_camera_shm_ns == 1000  # 8000 - 7000
        assert durations.idle_before_copy_to_multiframe_shm_ns == 1000  # 9000 - 8000
        assert durations.stored_in_multiframe_shm_ns == 2000  # 11000 - 9000
        assert durations.during_copy_from_multiframe_shm_ns == 1000  # 11000 - 10000

        # Test higher-level category timing metrics
        assert durations.total_frame_acquisition_time_ns == 3000  # 5000 - 2000
        assert durations.total_ipc_travel_time_ns == 6000  # 11000 - 5000
        assert durations.total_camera_to_recorder_time_ns == 8500  # 11000 - 2500

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
            pre_retrieve_from_camera_shm_ns=7000,
            post_retrieve_from_camera_shm_ns=8000,
            pre_copy_to_multiframe_shm_ns=9000,
            pre_retrieve_from_multiframe_shm_ns=10000,
            post_retrieve_from_multiframe_shm_ns=11000
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
        assert record_array.pre_copy_to_camera_shm_ns[0] == 6000
        assert record_array.pre_retrieve_from_camera_shm_ns[0] == 7000
        assert record_array.post_retrieve_from_camera_shm_ns[0] == 8000
        assert record_array.pre_copy_to_multiframe_shm_ns[0] == 9000
        assert record_array.pre_retrieve_from_multiframe_shm_ns[0] == 10000
        assert record_array.post_retrieve_from_multiframe_shm_ns[0] == 11000

        # Convert back to FrameTimestamps
        reconstructed = FrameTimestamps.from_numpy_record_array(record_array)

        # Check that the reconstructed object has the same values
        assert reconstructed.frame_initialized_ns == original.frame_initialized_ns
        assert reconstructed.pre_frame_grab_ns == original.pre_frame_grab_ns
        assert reconstructed.post_frame_grab_ns == original.post_frame_grab_ns
        assert reconstructed.pre_frame_retrieve_ns == original.pre_frame_retrieve_ns
        assert reconstructed.post_frame_retrieve_ns == original.post_frame_retrieve_ns
        assert reconstructed.pre_copy_to_camera_shm_ns == original.pre_copy_to_camera_shm_ns
        assert reconstructed.pre_retrieve_from_camera_shm_ns == original.pre_retrieve_from_camera_shm_ns
        assert reconstructed.post_retrieve_from_camera_shm_ns == original.post_retrieve_from_camera_shm_ns
        assert reconstructed.pre_copy_to_multiframe_shm_ns == original.pre_copy_to_multiframe_shm_ns
        assert reconstructed.pre_retrieve_from_multiframe_shm_ns == original.pre_retrieve_from_multiframe_shm_ns
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

    def test_negative_durations_for_unset_values(self):
        """Test that duration metrics return -1 when timestamps are not set."""
        timebase = TimebaseMapping()
        timestamps = FrameTimestamps(timebase_mapping=timebase)
        durations = timestamps.durations

        # All metrics should return -1 since no timestamps are set (except frame_initialized_ns)
        assert durations.idle_before_grab_ns == -1
        assert durations.during_frame_grab_ns == -1
        assert durations.idle_before_retrieve_ns == -1
        assert durations.during_frame_retrieve_ns == -1
        assert durations.idle_before_copy_to_camera_shm_ns == -1
        assert durations.stored_in_camera_shm_ns == -1
        assert durations.during_copy_from_camera_shm_ns == -1
        assert durations.idle_before_copy_to_multiframe_shm_ns == -1
        assert durations.stored_in_multiframe_shm_ns == -1
        assert durations.during_copy_from_multiframe_shm_ns == -1
        assert durations.total_frame_acquisition_time_ns == -1
        assert durations.total_ipc_travel_time_ns == -1
        assert durations.total_camera_to_recorder_time_ns == -1

        # Test to_dict method
        durations_dict = durations.model_dump(exclude={"timestamps"})
        assert all(value == -1 for value in durations_dict.values())



    def test_controlled_timing_simulation(self):
        """Test creating a dummy timestamp with controlled timing and verify durations."""
        # Create a controlled test that doesn't rely on actual timing
        timebase = TimebaseMapping()
        timestamps = FrameTimestamps(timebase_mapping=timebase)

        # Set timestamps with fixed increments instead of using sleep
        base_time = 1_000_000_000  # 1 second in ns
        timestamps.frame_initialized_ns = base_time
        timestamps.pre_frame_grab_ns = base_time + 100_000_000  # +100ms
        timestamps.post_frame_grab_ns = base_time + 300_000_000  # +300ms (+200ms from previous)
        timestamps.pre_frame_retrieve_ns = base_time + 600_000_000  # +600ms (+300ms from previous)
        timestamps.post_frame_retrieve_ns = base_time + 1_000_000_000  # +1000ms (+400ms from previous)
        timestamps.pre_copy_to_camera_shm_ns = base_time + 1_500_000_000  # +1500ms (+500ms from previous)
        timestamps.pre_retrieve_from_camera_shm_ns = base_time + 2_100_000_000  # +2100ms (+600ms from previous)
        timestamps.post_retrieve_from_camera_shm_ns = base_time + 2_800_000_000  # +2800ms (+700ms from previous)
        timestamps.pre_copy_to_multiframe_shm_ns = base_time + 3_600_000_000  # +3600ms (+800ms from previous)
        timestamps.pre_retrieve_from_multiframe_shm_ns = base_time + 4_500_000_000  # +4500ms (+900ms from previous)
        timestamps.post_retrieve_from_multiframe_shm_ns = base_time + 5_500_000_000  # +5500ms (+1000ms from previous)

        # Calculate durations
        durations = timestamps.durations

        # Verify durations are exactly as expected (since we're using fixed values)
        assert durations.idle_before_grab_ns == 100_000_000  # 100ms
        assert durations.during_frame_grab_ns == 200_000_000  # 200ms
        assert durations.idle_before_retrieve_ns == 300_000_000  # 300ms
        assert durations.during_frame_retrieve_ns == 400_000_000  # 400ms
        assert durations.idle_before_copy_to_camera_shm_ns == 500_000_000  # 500ms
        assert durations.during_copy_from_camera_shm_ns == 700_000_000  # 700ms
        assert durations.stored_in_camera_shm_ns == 1_300_000_000  # 1300ms (from pre_copy_to_camera_shm to post_retrieve_from_camera_shm)
        assert durations.idle_before_copy_to_multiframe_shm_ns == 800_000_000  # 800ms
        assert durations.during_copy_from_multiframe_shm_ns == 1_000_000_000  # 1000ms
        assert durations.stored_in_multiframe_shm_ns == 1_900_000_000  # 1900ms (from pre_copy_to_multiframe_shm to post_retrieve_from_multiframe_shm)

        # Check total_frame_acquisition_time_ns (should be 900ms = 1000ms - 100ms)
        assert durations.total_frame_acquisition_time_ns == 900_000_000  # post_frame_retrieve_ns - pre_frame_grab_ns

        # Check total_ipc_travel_time_ns (should be 4500ms = 5500ms - 1000ms)
        assert durations.total_ipc_travel_time_ns == 4_500_000_000  # post_retrieve_from_multiframe_shm_ns - post_frame_retrieve_ns

        # Check total_camera_to_recorder_time_ns (should be 5300ms = 5500ms - 200ms)
        # Note: timestamp_ns is (pre_frame_grab_ns + post_frame_grab_ns) // 2 = (100ms + 300ms) // 2 = 200ms
        assert durations.total_camera_to_recorder_time_ns == 5_300_000_000  # post_retrieve_from_multiframe_shm_ns - timestamp_ns