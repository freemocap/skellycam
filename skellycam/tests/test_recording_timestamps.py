import pytest
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock

from skellycam.core.frame_payloads.recording_timestamps import RecordingTimestamps
from skellycam.core.frame_payloads.multiframe_timestamps import MultiframeTimestamps
from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.utilities.sample_statistics import DescriptiveStatistics


class TestRecordingTimestamps:
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

        # Create MultiframeTimestamps instances
        self.multiframe_timestamps1 = MultiframeTimestamps(
            frame_timestamps=self.frame_timestamps,
            principal_camera_id="camera1"
        )

        # Create a second MultiframeTimestamps with slightly different values
        self.camera1_timestamps2 = FrameLifespanTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=11000,
            pre_grab_ns=12000,
            post_grab_ns=13000,
            pre_retrieve_ns=14000,
            post_retrieve_ns=15000,
            copy_to_camera_shm_ns=16000,
            retrieve_from_camera_shm_ns=17000,
            copy_to_multiframe_shm_ns=18000,
            retrieve_from_multiframe_shm_ns=19000
        )

        self.camera2_timestamps2 = FrameLifespanTimestamps(
            timebase_mapping=self.timebase,
            frame_initialized_ns=11500,
            pre_grab_ns=12500,
            post_grab_ns=13500,
            pre_retrieve_ns=14500,
            post_retrieve_ns=15500,
            copy_to_camera_shm_ns=16500,
            retrieve_from_camera_shm_ns=17500,
            copy_to_multiframe_shm_ns=18500,
            retrieve_from_multiframe_shm_ns=19500
        )

        self.frame_timestamps2 = {
            "camera1": self.camera1_timestamps2,
            "camera2": self.camera2_timestamps2
        }

        self.multiframe_timestamps2 = MultiframeTimestamps(
            frame_timestamps=self.frame_timestamps2,
            principal_camera_id="camera1"
        )

        # Create a RecordingTimestamps instance with the multiframe timestamps
        self.recording_timestamps = RecordingTimestamps(
            multiframe_timestamps=[self.multiframe_timestamps1, self.multiframe_timestamps2]
        )

        # Create a mock MultiFramePayload for testing add_multiframe
        self.mock_multiframe = MagicMock()
        self.mock_multiframe.frames = {
            "camera1": MagicMock(timestamps=self.camera1_timestamps),
            "camera2": MagicMock(timestamps=self.camera2_timestamps)
        }
        self.mock_multiframe.principal_camera_id = "camera1"

    def test_initialization(self):
        """Test that RecordingTimestamps initializes correctly."""
        # Test empty initialization
        empty_recording = RecordingTimestamps()
        assert empty_recording.multiframe_timestamps == []
        assert empty_recording.number_of_recorded_frames == 0

        # Test initialization with multiframe timestamps
        assert self.recording_timestamps.multiframe_timestamps == [self.multiframe_timestamps1,
                                                                   self.multiframe_timestamps2]
        assert self.recording_timestamps.number_of_recorded_frames == 2

    def test_add_multiframe(self):
        """Test adding a multiframe payload to the recording timestamps."""
        # Create a new empty RecordingTimestamps
        recording = RecordingTimestamps()
        assert recording.number_of_recorded_frames == 0

        # Add a multiframe payload
        with patch('skellycam.core.frame_payloads.multiframe_timestamps.MultiframeTimestamps.from_multiframe',
                   return_value=self.multiframe_timestamps1):
            recording.add_multiframe(self.mock_multiframe)

        # Check that the multiframe was added
        assert recording.number_of_recorded_frames == 1
        assert recording.multiframe_timestamps[0] == self.multiframe_timestamps1

    def test_first_timestamp(self):
        """Test getting the first timestamp."""
        # Check that the first timestamp is correct
        assert self.recording_timestamps.first_timestamp == self.multiframe_timestamps1

        # Test with empty recording
        empty_recording = RecordingTimestamps()
        with pytest.raises(ValueError, match="No multiframe timestamps available"):
            _ = empty_recording.first_timestamp

    def test_recording_start_local_unix_ms(self):
        """Test getting the recording start timestamp."""
        # Create a custom MultiframeTimestamps with a known frame_initialized_local_unix_ms value
        custom_frame_timestamps = FrameLifespanTimestamps(
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

        # Mock the frame_initialized_local_unix_ms property
        with patch.object(custom_frame_timestamps.__class__, 'frame_initialized_local_unix_ms',
                          property(lambda self: 1000)):
            custom_multiframe = MultiframeTimestamps(
                frame_timestamps={"camera1": custom_frame_timestamps},
                principal_camera_id="camera1"
            )

            custom_recording = RecordingTimestamps(
                multiframe_timestamps=[custom_multiframe]
            )

            # Test the property
            assert custom_recording.recording_start_local_unix_ms == 1000


    def test_timestamps_local_unix_ms(self):
        """Test getting the timestamps relative to the first frame."""
        # Create a test instance with mocked values
        with patch.object(RecordingTimestamps, 'recording_start_local_unix_ms',
                          property(lambda self: 500)):
            # Mock the timestamp_local_unix_ms.mean values
            mock_stats1 = MagicMock()
            mock_stats1.mean = 1000
            mock_stats2 = MagicMock()
            mock_stats2.mean = 2000

            # Store references to the multiframe timestamps instances
            mf1 = self.multiframe_timestamps1
            mf2 = self.multiframe_timestamps2

            # Create test multiframes with mocked timestamp_local_unix_ms
            with patch.object(MultiframeTimestamps, 'timestamp_local_unix_ms',
                              property(
                                  lambda self: mock_stats1 if self is mf1 else mock_stats2)):
                # Test the property
                timestamps = self.recording_timestamps.timestamps_local_unix_ms
                assert timestamps == [500, 1500]  # 1000-500, 2000-500
    def test_frame_durations_ms(self):
        """Test calculating frame durations."""
        # Create a test instance with mocked timestamps_local_unix_ms
        with patch.object(RecordingTimestamps, 'timestamps_local_unix_ms',
                          property(lambda self: [0, 10, 25])):
            # Test the property
            durations = self.recording_timestamps.frame_durations_ms
            assert len(durations) == 3
            assert np.isnan(durations[0])  # First value should be NaN
            assert durations[1] == 10  # 10 - 0
            assert durations[2] == 15  # 25 - 10

    def test_frames_per_second(self):
        """Test calculating frames per second."""
        # Create a test instance with mocked frame_durations_ms
        with patch.object(RecordingTimestamps, 'frame_durations_ms',
                          property(lambda self: [np.nan, 10, 20, 0, -5])):
            # Test the property
            fps = self.recording_timestamps.frames_per_second
            assert len(fps) == 2  # Only positive durations should be included
            assert fps[0] == 1e6 / 10  # 1e6 / 10
            assert fps[1] == 1e6 / 20  # 1e6 / 20

    def test_fps_stats(self):
        """Test calculating FPS statistics."""
        # Create a test instance with mocked frames_per_second
        with patch.object(RecordingTimestamps, 'frames_per_second',
                          property(lambda self: [100, 200])):
            with patch('skellycam.utilities.sample_statistics.DescriptiveStatistics.from_samples') as mock_from_samples:
                # Test the property
                _ = self.recording_timestamps.fps_stats
                mock_from_samples.assert_called_once_with(
                    samples=[100, 200],
                    name="frames_per_second",
                    units="Hz"
                )

    def test_frame_duration_stats(self):
        """Test calculating frame duration statistics."""
        # Create a test instance with mocked frame_durations_ms
        with patch.object(RecordingTimestamps, 'frame_durations_ms',
                          property(lambda self: [np.nan, 10, 20])):
            with patch('skellycam.utilities.sample_statistics.DescriptiveStatistics.from_samples') as mock_from_samples:
                # Test the property
                _ = self.recording_timestamps.frame_duration_stats
                mock_from_samples.assert_called_once_with(
                    samples=[np.nan, 10, 20],
                    name="frame_durations_ms",
                    units="milliseconds"
                )


    def test_inter_camera_grab_range_stats(self):
        """Test calculating inter-camera grab range statistics."""
        # Create minimal valid MultiframeTimestamps instances
        frame_timestamps = {
            "camera1": FrameLifespanTimestamps(
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
        }

        mf1 = MultiframeTimestamps(
            frame_timestamps=frame_timestamps,
            principal_camera_id="camera1"
        )

        mf2 = MultiframeTimestamps(
            frame_timestamps=frame_timestamps,
            principal_camera_id="camera1"
        )

        test_recording = RecordingTimestamps(
            multiframe_timestamps=[mf1, mf2]
        )

        # Patch the inter_camera_grab_range_ms property
        with patch.object(MultiframeTimestamps, 'inter_camera_grab_range_ms',
                          new_callable=PropertyMock,
                          side_effect=[5, 10]):
            with patch('skellycam.utilities.sample_statistics.DescriptiveStatistics.from_samples') as mock_from_samples:
                # Test the property
                _ = test_recording.inter_camera_grab_range_stats
                mock_from_samples.assert_called_once_with(
                    samples=[5, 10],
                    name="inter_camera_grab_range_ms",
                    units="milliseconds"
                )

    def test_timing_stats_properties(self):
        """Test all the timing statistics properties."""
        # List of all timing statistics properties that follow the same pattern
        timing_properties = [
            "idle_before_grab_duration_stats",
            "frame_grab_duration_stats",
            "idle_before_retrieve_duration_stats",
            "frame_retrieve_duration_stats",
            "idle_before_copy_to_camera_shm_duration_stats",
            "idle_in_camera_shm_duration_stats",
            "idle_before_copy_to_multiframe_shm_duration_stats",
            "idle_in_multiframe_shm_duration_stats",
            "total_frame_acquisition_duration_stats",
            "total_ipc_travel_duration_stats"
        ]

        # For each property, we'll test it individually
        for prop_name in timing_properties:
            # Get the corresponding property name in MultiframeTimestamps (without _stats suffix but with _ms suffix)
            mf_prop_name = prop_name.replace("_stats", "") + "_ms"

            # Create a test instance with the real multiframes
            test_recording = RecordingTimestamps(
                multiframe_timestamps=[self.multiframe_timestamps1, self.multiframe_timestamps2]
            )

            # Mock the RecordingTimestamps.multiframe_timestamps property to return a list with mocked values
            mock_mf1 = MagicMock()
            mock_mf2 = MagicMock()

            # Set the property values on the mock objects
            setattr(mock_mf1, mf_prop_name, 5)
            setattr(mock_mf2, mf_prop_name, 10)

            # Replace the multiframe_timestamps list with our mocked objects
            with patch.object(test_recording, 'multiframe_timestamps', [mock_mf1, mock_mf2]):
                with patch(
                        'skellycam.utilities.sample_statistics.DescriptiveStatistics.from_samples') as mock_from_samples:
                    # Access the property
                    _ = getattr(test_recording, prop_name)

                    # Check that DescriptiveStatistics.from_samples was called with the right arguments
                    mock_from_samples.assert_called_once_with(
                        samples=[5, 10],
                        name=mf_prop_name,
                        units="milliseconds"
                    )