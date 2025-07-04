import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.camera_group.timestamps import FrameTimestamps
from skellycam.core.camera_group.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.camera_group.timestamps import RecordingTimestamps
from skellycam.core.camera_group.timestamps import TimebaseMapping
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics


class TestRecordingTimestamps:
    def setup_method(self):
        """Set up test fixtures for each test method."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create a recording info object
        self.recording_info = RecordingInfo(
            recording_name="test_recording",
            recording_directory=self.temp_dir.name
        )

        # Create a timebase mapping for use in tests
        self.timebase = TimebaseMapping()

        # Base time for timestamps (1 second in ns)
        self.base_time = 1_000_000_000

        # Create simulated timestamps for multiple cameras
        self.create_simulated_timestamps()

        # Create a RecordingTimestamps instance
        self.recording_timestamps = RecordingTimestamps(
            recording_info=self.recording_info,
            recording_start_ns=self.base_time - 500_000_000  # 500ms before base time
        )

        # Add the simulated multiframes to the recording timestamps
        for mf in self.multiframes:
            self.recording_timestamps.add_multiframe(mf)

    def teardown_method(self):
        """Clean up after each test method."""
        self.temp_dir.cleanup()

    def create_simulated_timestamps(self):
        """Create simulated timestamps for multiple cameras at 30fps."""
        # We'll create 10 frames at 30fps (33.33ms between frames)
        self.num_frames = 10
        self.frame_interval_ns = 33_333_333  # ~30fps

        # Create 4 cameras with slightly different timing patterns
        self.camera_ids = ["camera1", "camera2", "camera3", "camera4"]

        # Create multiframes
        self.multiframes = []

        for frame_num in range(self.num_frames):
            # Create a mock MultiFramePayload
            mock_multiframe = MagicMock()
            mock_multiframe.frames = {}
            mock_multiframe.multi_frame_number = frame_num

            # Current frame time
            current_time = self.base_time + frame_num * self.frame_interval_ns

            # Create frame timestamps for each camera with slight variations
            for i, camera_id in enumerate(self.camera_ids):
                # Add slight offset for each camera (0ms, 1ms, 2ms, 3ms)
                camera_offset = i * 1_000_000

                # Create timestamps with controlled values
                frame_ts = FrameTimestamps(
                    timebase_mapping=self.timebase,
                    frame_initialized_ns=current_time + camera_offset,
                    pre_frame_grab_ns=current_time + camera_offset + 1_000_000,  # +1ms
                    post_frame_grab_ns=current_time + camera_offset + 3_000_000,  # +3ms (+2ms from pre_grab)
                    pre_frame_retrieve_ns=current_time + camera_offset + 4_000_000,  # +4ms (+1ms from post_grab)
                    post_frame_retrieve_ns=current_time + camera_offset + 6_000_000,  # +6ms (+2ms from pre_retrieve)
                    pre_copy_to_camera_shm_ns=current_time + camera_offset + 7_000_000,
                    # +7ms (+1ms from post_retrieve)
                    pre_retrieve_from_camera_shm_ns=current_time + camera_offset + 8_000_000,
                    # +8ms (+1ms from pre_copy)
                    post_retrieve_from_camera_shm_ns=current_time + camera_offset + 9_000_000,
                    # +9ms (+1ms from pre_retrieve)
                    pre_copy_to_multiframe_shm_ns=current_time + camera_offset + 10_000_000,
                    # +10ms (+1ms from post_retrieve)
                    pre_retrieve_from_multiframe_shm_ns=current_time + camera_offset + 11_000_000,
                    # +11ms (+1ms from pre_copy)
                    post_retrieve_from_multiframe_shm_ns=current_time + camera_offset + 12_000_000,
                    # +12ms (+1ms from pre_retrieve)
                )

                # Create a mock frame with the timestamps
                mock_frame = MagicMock()
                mock_frame.frame_metadata = MagicMock(timestamps=frame_ts)
                mock_multiframe.frames[camera_id] = mock_frame

            # Set the earliest timestamp for the multiframe
            mock_multiframe.earliest_timestamp_ns = min(
                [frame.frame_metadata.timestamps.pre_frame_grab_ns for frame in mock_multiframe.frames.values()]
            )

            self.multiframes.append(mock_multiframe)

    def test_initialization(self):
        """Test that RecordingTimestamps initializes correctly."""
        # Check that the recording_info is set correctly
        assert self.recording_timestamps.recording_info == self.recording_info

        # Check that the recording_start_ns is set correctly
        assert self.recording_timestamps.recording_start_ns == self.base_time - 500_000_000

        # Check that the multiframe_timestamps list is populated
        assert len(self.recording_timestamps.multiframe_timestamps) == self.num_frames

        # Check that each multiframe_timestamps is a MultiFrameTimestamps object
        for mf_ts in self.recording_timestamps.multiframe_timestamps:
            assert isinstance(mf_ts, MultiFrameTimestamps)

    def test_number_of_recorded_frames(self):
        """Test the number_of_recorded_frames property."""
        assert self.recording_timestamps.number_of_recorded_frames == self.num_frames

    def test_number_of_cameras(self):
        """Test the number_of_cameras property."""
        assert self.recording_timestamps.number_of_cameras == len(self.camera_ids)

    def test_total_duration_sec(self):
        """Test the total_duration_sec property."""
        # Expected duration: (num_frames - 1) * frame_interval in seconds
        expected_duration = (self.num_frames - 1) * (self.frame_interval_ns / 1e9)
        assert self.recording_timestamps.total_duration_sec == pytest.approx(expected_duration)

    def test_first_timestamp(self):
        """Test the first_timestamp property."""
        assert self.recording_timestamps.first_timestamp == self.recording_timestamps.multiframe_timestamps[0]

    def test_timestamps_ms(self):
        """Test the timestamps_ms property."""
        timestamps_ms = self.recording_timestamps.timestamps_ms

        # Check that we have the correct number of timestamps
        assert len(timestamps_ms) == self.num_frames

        # Check that the timestamps are increasing
        for i in range(1, len(timestamps_ms)):
            assert timestamps_ms[i] > timestamps_ms[i - 1]

        # Check that the intervals are approximately correct (33.33ms for 30fps)
        for i in range(1, len(timestamps_ms)):
            interval = timestamps_ms[i] - timestamps_ms[i - 1]
            assert interval == pytest.approx(self.frame_interval_ns / 1e6, abs=0.1)

    def test_frame_durations_ms(self):
        """Test the frame_durations_ms property."""
        durations = self.recording_timestamps.frame_durations_ms

        # Check that we have the correct number of durations
        assert len(durations) == self.num_frames

        # First duration should be NaN
        assert np.isnan(durations[0])

        # Check that the remaining durations are approximately correct (33.33ms for 30fps)
        for i in range(1, len(durations)):
            assert durations[i] == pytest.approx(self.frame_interval_ns / 1e6, abs=0.1)

    def test_frames_per_second(self):
        """Test the frames_per_second property."""
        fps = self.recording_timestamps.frames_per_second

        # Check that we have the correct number of fps values (num_frames - 1 since first is NaN)
        assert len(fps) == self.num_frames - 1

        # Check that the fps values are approximately correct (30fps)
        for fps_value in fps:
            assert fps_value == pytest.approx(30.0, abs=0.1)

    def test_framerate_stats(self):
        """Test the framerate_stats property."""
        stats = self.recording_timestamps.framerate_stats

        # Check that it's a DescriptiveStatistics object
        assert isinstance(stats, DescriptiveStatistics)

        # Check that the mean is approximately 30fps
        assert stats.mean == pytest.approx(30.0, abs=0.1)

        # Check that the standard deviation is small (consistent framerate)
        assert stats.standard_deviation < 0.1

    def test_frame_duration_stats(self):
        """Test the frame_duration_stats property."""
        stats = self.recording_timestamps.frame_duration_stats

        # Check that it's a DescriptiveStatistics object
        assert isinstance(stats, DescriptiveStatistics)

        # Check that the mean is approximately 33.33ms (for 30fps)
        assert stats.mean == pytest.approx(33.33, abs=0.1)

    def test_inter_camera_grab_range_stats(self):
        """Test the inter_camera_grab_range_stats property."""
        stats = self.recording_timestamps.inter_camera_grab_range_stats

        # Check that it's a DescriptiveStatistics object
        assert isinstance(stats, DescriptiveStatistics)

        # The range should be 3ms (difference between camera1 and camera4)
        assert stats.mean == pytest.approx(3.0, abs=0.1)

    def test_timestamps_by_camera_id(self):
        """Test the timestamps_by_camera_id property."""
        camera_timestamps = self.recording_timestamps.timestamps_by_camera_id

        # Check that we have timestamps for each camera
        assert set(camera_timestamps.keys()) == set(self.camera_ids)

        # Check that each camera has the correct number of timestamps
        for camera_id in self.camera_ids:
            assert len(camera_timestamps[camera_id]) == self.num_frames

            # Check that each timestamp is a FrameTimestamps object
            for ts in camera_timestamps[camera_id]:
                assert isinstance(ts, FrameTimestamps)

    def test_frame_numbers(self):
        """Test the frame_numbers property."""
        frame_numbers = self.recording_timestamps.frame_numbers

        # Check that we have the correct number of frame numbers
        assert len(frame_numbers) == self.num_frames

        # Check that the frame numbers are sequential
        assert frame_numbers == list(range(self.num_frames))

    def test_to_stats(self):
        """Test the to_stats method."""
        stats = self.recording_timestamps.to_stats()

        # Print the stats object string representation
        print("\n=== RECORDING STATS ===")
        print(stats)

        # Check that the stats object has the correct properties
        assert stats.recording_name == self.recording_info.recording_name
        assert stats.number_of_cameras == len(self.camera_ids)
        assert stats.number_of_frames == self.num_frames
        assert stats.total_duration_sec == pytest.approx(self.recording_timestamps.total_duration_sec)

        # Check that the framerate stats match
        assert stats.framerate_stats.mean == pytest.approx(self.recording_timestamps.framerate_stats.mean)

    @patch('skellycam.core.timestamps.recording_timestamps.logger')
    def test_save_timestamps(self, mock_logger):
        """Test the save_timestamps method."""
        # Call the method
        self.recording_timestamps.save_timestamps()

        # Check that the CSV files were created
        mf_csv_path = Path(
            f"{self.recording_info.timestamps_folder}/{self.recording_info.recording_name}_timestamps.csv")
        assert mf_csv_path.exists()

        # Print the contents of the multiframe CSV file
        print("\n=== MULTIFRAME CSV CONTENTS ===")
        with open(mf_csv_path, 'r') as f:
            mf_csv_content = f.read()
            print(mf_csv_content)

            # Verify the CSV has proper column headers (not tuples)
            first_line = mf_csv_content.split('\n')[0]
            assert "recording_frame_number" in first_line
            assert "timestamp.from_recording_start.sec" in first_line
            assert "duration.total_frame_acquisition.mean.ms" in first_line

            # Verify the CSV doesn't contain tuple representations
            assert "('multiframe_number'" not in mf_csv_content

        # Check that the stats JSON file was created
        stats_json_path = Path(
            f"{self.recording_info.timestamps_folder}/{self.recording_info.recording_name}_stats.json")
        assert stats_json_path.exists()

        # Print a sample of the stats JSON file
        print("\n=== STATS JSON SAMPLE ===")
        with open(stats_json_path, 'r') as f:
            stats_content = f.read()
            print(stats_content[:500] + "..." if len(stats_content) > 500 else stats_content)

        # Check that camera CSV files were created
        for camera_id in self.camera_ids:
            camera_csv_path = Path(
                f"{self.recording_info.camera_timestamps_folder}/{self.recording_info.recording_name}_camera_{camera_id}_timestamps.csv")
            assert camera_csv_path.exists()

            # Print the contents of the first camera CSV file only
            if camera_id == self.camera_ids[0]:
                print(f"\n=== CAMERA {camera_id} CSV CONTENTS ===")
                with open(camera_csv_path, 'r') as f:
                    camera_csv_content = f.read()
                    print(camera_csv_content)

                    # Verify the CSV has proper column headers (not tuples)
                    first_line = camera_csv_content.split('\n')[0]
                    assert "recording_frame_number" in first_line
                    assert "timestamp.from_recording_start.sec" in first_line
                    assert "duration.total_frame_acquisition.ns" in first_line

                    # Verify the CSV doesn't contain tuple representations
                    assert "('recording_frame_number'" not in camera_csv_content

        # Check that the logger was called
        assert mock_logger.info.call_count >= 2

    def test_to_mf_dataframe(self):
        """Test the to_mf_dataframe method."""
        df = self.recording_timestamps.to_mf_dataframe()

        # Check that it's a pandas DataFrame
        assert isinstance(df, pd.DataFrame)

        # Print the dataframe
        print("\n=== MULTIFRAME DATAFRAME ===")
        print(df.head())
        print("\nDataFrame info:")
        print(df.info())
        print("\nDataFrame description:")
        print(df.describe())

        # Check that it has the correct number of rows
        assert len(df) == self.num_frames

        # Check that the columns match the expected format from MultiFrameTimestampsCSVRow:
        # Verify some key columns exist with proper names
        assert "recording_frame_number" in df.columns
        assert "connection_frame_number" in df.columns
        assert "timestamp.from_recording_start.sec" in df.columns
        assert "duration.total_frame_acquisition.mean.ms" in df.columns

        # Verify the values are not tuples
        for col in df.columns:
            sample_value = df[col].iloc[0]
            assert not isinstance(sample_value, tuple)
    def test_to_camera_dataframes(self):
        """Test the to_camera_dataframes method."""
        dfs = self.recording_timestamps.to_camera_dataframes()

        # Check that we have a dataframe for each camera
        assert set(dfs.keys()) == set(self.camera_ids)

        # Print the first camera dataframe
        first_camera = self.camera_ids[0]
        print(f"\n=== CAMERA {first_camera} DATAFRAME ===")
        print(dfs[first_camera].head())
        print("\nDataFrame info:")
        print(dfs[first_camera].info())
        print("\nDataFrame description:")
        print(dfs[first_camera].describe())

        # Check that each dataframe is a pandas DataFrame
        for camera_id in self.camera_ids:
            assert isinstance(dfs[camera_id], pd.DataFrame)

            # Check that each dataframe has the correct number of rows
            assert len(dfs[camera_id]) == self.num_frames

            # Check that the index is the frame numbers
            assert list(dfs[camera_id].index) == list(range(self.num_frames))

            # Check that the columns match the expected format from FrameTimestampsCSVRow
            # Verify some key columns exist with proper names
            assert "recording_frame_number" in dfs[camera_id].columns
            assert "timestamp.from_recording_start.sec" in dfs[camera_id].columns
            assert "duration.total_frame_acquisition.ns" in dfs[camera_id].columns

            # Verify the values are not tuples
            for col in dfs[camera_id].columns:
                sample_value = dfs[camera_id][col].iloc[0]
                assert not isinstance(sample_value, tuple)

    def test_empty_multiframe_timestamps(self):
        """Test behavior with empty multiframe_timestamps."""
        empty_recording = RecordingTimestamps(
            recording_info=self.recording_info,
            recording_start_ns=self.base_time
        )

        # total_duration_sec should be 0.0
        assert empty_recording.total_duration_sec == 0.0

        # first_timestamp should raise ValueError
        with pytest.raises(ValueError):
            _ = empty_recording.first_timestamp

        # timestamps_ms should return an empty list
        assert empty_recording.timestamps_ms == []

        # frame_durations_ms should return an empty list
        assert empty_recording.frame_durations_ms == []

        # save_timestamps should raise ValueError
        with pytest.raises(ValueError):
            empty_recording.save_timestamps()

    def test_add_multiframe_sets_recording_start_ns(self):
        """Test that add_multiframe sets recording_start_ns if it's None."""
        recording = RecordingTimestamps(
            recording_info=self.recording_info,
            recording_start_ns=None
        )

        # Add a multiframe
        recording.add_multiframe(self.multiframes[0])

        # Check that recording_start_ns was set to the earliest timestamp
        assert recording.recording_start_ns == self.multiframes[0].earliest_timestamp_ns

    def test_all_duration_stats_properties(self):
        """Test all duration statistics properties."""
        # Test a few representative duration statistics properties

        # idle_before_grab_duration_stats
        stats = self.recording_timestamps.idle_before_grab_duration_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(1.0, abs=0.1)  # 1ms

        # during_frame_grab_stats
        stats = self.recording_timestamps.during_frame_grab_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(2.0, abs=0.1)  # 2ms

        # idle_before_retrieve_duration_stats
        stats = self.recording_timestamps.idle_before_retrieve_duration_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(1.0, abs=0.1)  # 1ms

        # during_frame_retrieve_stats
        stats = self.recording_timestamps.during_frame_retrieve_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(2.0, abs=0.1)  # 2ms

        # total_frame_acquisition_time_stats
        stats = self.recording_timestamps.total_frame_acquisition_time_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(5.0, abs=0.1)  # 5ms (from pre_grab to post_retrieve)

        # total_ipc_travel_time_stats
        stats = self.recording_timestamps.total_ipc_travel_time_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(6.0,
                                           abs=0.1)  # 6ms (from post_retrieve to post_retrieve_from_multiframe_shm)

        # total_camera_to_recorder_time_stats
        stats = self.recording_timestamps.total_camera_to_recorder_time_stats
        assert isinstance(stats, DescriptiveStatistics)
        assert stats.mean == pytest.approx(10.0,
                                           abs=0.1)  # 10ms (from timestamp_ns to post_retrieve_from_multiframe_shm)