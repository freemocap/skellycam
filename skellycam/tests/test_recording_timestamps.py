from unittest.mock import MagicMock

import numpy as np

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.timestamps.multiframe_timestamps import MultiFrameTimestamps
from skellycam.core.timestamps.recording_timestamps import RecordingTimestampsStats, RecordingTimestamps
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping


class TestRecordingTimestampsStats:
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
        self.frame_timestamps1 = {
            "camera1": self.camera1_timestamps,
            "camera2": self.camera2_timestamps
        }

        # Recording start time (for relative timing)
        self.recording_start_time_ns = base_time - 500_000_000  # 500ms before base time

        # Create a MultiframeTimestamps instance
        self.multiframe_timestamps1 = MultiFrameTimestamps(
            frame_timestamps=self.frame_timestamps1,
            recording_start_time_ns=self.recording_start_time_ns,
            multiframe_number=1
        )

        # Create a second set of timestamps with slightly different values
        # Camera 1 timestamps (second frame)
        self.camera1_timestamps2 = FrameTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=base_time + 2_000_000_000,  # +2s from base
            pre_frame_grab_ns=base_time + 2_100_000_000,  # +2.1s
            post_frame_grab_ns=base_time + 2_300_000_000,  # +2.3s
            pre_frame_retrieve_ns=base_time + 2_400_000_000,  # +2.4s
            post_frame_retrieve_ns=base_time + 2_600_000_000,  # +2.6s
            pre_copy_to_camera_shm_ns=base_time + 2_700_000_000,  # +2.7s
            pre_retrieve_from_camera_shm_ns=base_time + 2_800_000_000,  # +2.8s
            post_retrieve_from_camera_shm_ns=base_time + 2_900_000_000,  # +2.9s
            pre_copy_to_multiframe_shm_ns=base_time + 3_000_000_000,  # +3.0s
            pre_retrieve_from_multiframe_shm_ns=base_time + 3_100_000_000,  # +3.1s
            post_retrieve_from_multiframe_shm_ns=base_time + 3_200_000_000,  # +3.2s
        )

        # Camera 2 timestamps (second frame)
        self.camera2_timestamps2 = FrameTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=base_time + 2_050_000_000,  # +2.05s
            pre_frame_grab_ns=base_time + 2_150_000_000,  # +2.15s
            post_frame_grab_ns=base_time + 2_350_000_000,  # +2.35s
            pre_frame_retrieve_ns=base_time + 2_450_000_000,  # +2.45s
            post_frame_retrieve_ns=base_time + 2_650_000_000,  # +2.65s
            pre_copy_to_camera_shm_ns=base_time + 2_750_000_000,  # +2.75s
            pre_retrieve_from_camera_shm_ns=base_time + 2_850_000_000,  # +2.85s
            post_retrieve_from_camera_shm_ns=base_time + 2_950_000_000,  # +2.95s
            pre_copy_to_multiframe_shm_ns=base_time + 3_050_000_000,  # +3.05s
            pre_retrieve_from_multiframe_shm_ns=base_time + 3_150_000_000,  # +3.15s
            post_retrieve_from_multiframe_shm_ns=base_time + 3_250_000_000,  # +3.25s
        )

        self.frame_timestamps2 = {
            "camera1": self.camera1_timestamps2,
            "camera2": self.camera2_timestamps2
        }

        self.multiframe_timestamps2 = MultiFrameTimestamps(
            frame_timestamps=self.frame_timestamps2,
            recording_start_time_ns=self.recording_start_time_ns,
            multiframe_number=2
        )

        # Create a mock RecordingInfo
        self.recording_info = MagicMock(spec=RecordingInfo)
        self.recording_info.recording_name = "test_recording"
        self.recording_info.timestamps_folder = "test_timestamps"
        self.recording_info.camera_timestamps_folder = "test_camera_timestamps"

        # Create a RecordingTimestamps instance with the multiframe timestamps
        self.recording_timestamps = RecordingTimestamps(
            multiframe_timestamps=[self.multiframe_timestamps1, self.multiframe_timestamps2],
            recording_start_ns=self.recording_start_time_ns,
            recording_info=self.recording_info
        )

        # Create the actual RecordingTimestampsStats from the real RecordingTimestamps
        self.stats = self.recording_timestamps.to_stats()

    def test_from_recording_timestamps(self):
        """Test creating RecordingTimestampsStats from RecordingTimestamps."""
        # Use the actual recording_timestamps created in setup_method
        stats = RecordingTimestampsStats.from_recording_timestamps(self.recording_timestamps)

        # Check that the stats were created correctly
        assert stats.recording_name == "test_recording"
        assert stats.number_of_frames == 2

        # Verify that stats properties match the expected values from our controlled timestamps
        # Check framerate stats - the mean is NaN because there's only one valid frame duration
        # and the first one is NaN (no previous frame to calculate duration from)
        assert np.isnan(stats.framerate_stats.mean)

        # Check frame duration stats
        # Frame durations: [NaN, 2000ms]
        assert stats.frame_duration_stats.mean == 2000.0

        # Check inter-camera grab range (difference between camera timestamps)
        # Camera1: 200ms, Camera2: 250ms -> Range: 50ms
        assert stats.inter_camera_grab_range_ms.mean == 50.0

        # Check idle before grab (both cameras have 100ms)
        assert stats.idle_before_grab_ms.mean == 100.0

        # Check during frame grab (both cameras have 200ms)
        assert stats.during_frame_grab_ms.mean == 200.0

        # Check total frame acquisition time (500ms for both cameras)
        assert stats.total_frame_acquisition_time_ms.mean == 500.0

        # Check total IPC travel time (600ms for both cameras)
        assert stats.total_ipc_travel_time_ms.mean == 600.0

    def test_str_representation(self):
        """Test the string representation of RecordingTimestampsStats."""
        # Call the __str__ method on the actual stats object
        result = str(self.stats)

        # Check that the result is a non-empty string
        assert isinstance(result, str)
        assert len(result) > 0

        # Check that the result contains key information
        assert "Recording Statistics: test_recording" in result
        assert "Total Frames: 2" in result
        assert "FRAME TIMING STATISTICS" in result
        assert "FRAME ACQUISITION PIPELINE" in result
        assert "SUMMARY METRICS" in result

        # Check that it includes all the stages
        stages = [
            "Idle before grab",
            "Frame grab",
            "Idle before retrieve",
            "Frame retrieve",
            "Idle before copy to camera SHM",
            "Stored in camera SHM",
            "Idle before copy to multiframe SHM",
            "Stored in multiframe SHM"
        ]

        for stage in stages:
            assert stage in result

        # Check that it includes summary metrics
        assert "Total frame acquisition time" in result
        assert "Total IPC travel time" in result

        # Verify that actual values from our controlled timestamps appear in the output
        assert "100" in result  # idle_before_grab_ms
        assert "200" in result  # during_frame_grab_ms
        assert "500" in result  # total_frame_acquisition_time_ms
        assert "600" in result  # total_ipc_travel_time_ms
        assert "nan Hz" in result  # framerate_stats is NaN
        assert "2000.00 ms" in result  # frame_duration_stats