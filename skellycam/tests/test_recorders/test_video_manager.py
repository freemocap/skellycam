import shutil
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

import numpy as np

from skellycam.core.camera.config.camera_config import (
    CameraConfig,
    DEFAULT_RESOLUTION,
    DEFAULT_EXPOSURE_MODE,
    DEFAULT_EXPOSURE,
    DEFAULT_FRAMERATE,
    DEFAULT_ROTATION,
    DEFAULT_CAPTURE_FOURCC,
    DEFAULT_WRITER_FOURCC
)
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.frame_payloads.multiframes.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_manager import VideoManager
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.camera_group.timestamps import FrameTimestamps
from skellycam.core.camera_group.timestamps.full_timestamp import FullTimestamp
from skellycam.core.camera_group.timestamps import TimebaseMapping
from skellycam.core.types.type_overloads import CameraIdString, CameraIndex


class TestVideoManager(TestCase):
    def setUp(self):
        # Create a temporary directory for test videos
        self.temp_dir = tempfile.mkdtemp()

        # Create camera configs for multiple cameras
        self.camera_ids = [CameraIdString(f"test_camera_{i}") for i in range(2)]
        self.camera_configs = {}

        for i, camera_id in enumerate(self.camera_ids):
            self.camera_configs[camera_id] = CameraConfig(
                camera_id=camera_id,
                camera_index=CameraIndex(i),
                resolution=DEFAULT_RESOLUTION,
                exposure_mode=DEFAULT_EXPOSURE_MODE,
                exposure=DEFAULT_EXPOSURE,
                framerate=DEFAULT_FRAMERATE,
                rotation=DEFAULT_ROTATION,
                capture_fourcc=DEFAULT_CAPTURE_FOURCC,
                writer_fourcc=DEFAULT_WRITER_FOURCC
            )

        # Create a recording info
        self.recording_info = RecordingInfo(
            recording_name="test_recording",
            recording_directory=self.temp_dir,
            recording_start_timestamp=FullTimestamp.now()
        )

        # Create a timebase mapping for frame timestamps
        self.timebase_mapping = TimebaseMapping()

        # Create a video manager
        self.video_manager = VideoManager.create(
            recording_info=self.recording_info,
            camera_configs=self.camera_configs
        )

    def tearDown(self):
        # Clean up the temporary directory
        if hasattr(self, 'video_manager'):
            for recorder in self.video_manager.video_recorders.values():
                if recorder.video_writer is not None:
                    recorder.close()

        shutil.rmtree(self.temp_dir)

    def create_test_frame(self, camera_id: CameraIdString, frame_number: int,
                          color: tuple = (255, 0, 0)) -> FramePayload:
        """Helper method to create a test frame with specified camera, number and color"""
        camera_config = self.camera_configs[camera_id]
        height, width = camera_config.resolution.height, camera_config.resolution.width
        channels = camera_config.color_channels

        # Create a colored image
        image = np.zeros((height, width, channels), dtype=np.uint8)
        image[:, :] = color

        # Add frame number and camera ID as text in the center of the image
        import cv2
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = f"Camera {camera_id} - Frame {frame_number}"
        text_size = cv2.getTextSize(text, font, 1, 2)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        cv2.putText(image, text, (text_x, text_y), font, 1, (255, 255, 255), 2)

        # Create frame metadata
        frame_metadata = FrameMetadata(
            frame_number=frame_number,
            camera_config=camera_config,
            timestamps=FrameTimestamps(timebase_mapping=self.timebase_mapping)
        )

        # Set timestamps to simulate a real frame
        frame_metadata.timestamps.pre_frame_grab_ns = self.timebase_mapping.perf_counter_ns
        frame_metadata.timestamps.post_frame_grab_ns = self.timebase_mapping.perf_counter_ns + 10000  # 10 microseconds later

        return FramePayload(image=image, frame_metadata=frame_metadata)

    def create_multi_frame(self, frame_number: int) -> MultiFramePayload:
        """Helper method to create a multi-frame with frames from all cameras"""
        frames = {
            camera_id: self.create_test_frame(
                camera_id=camera_id,
                frame_number=frame_number,
                color=(50 * (i + 1), 0, 255 - 50 * (i + 1))
            )
            for i, camera_id in enumerate(self.camera_ids)
        }

        return MultiFramePayload(
            frames=frames,
            multi_frame_number=frame_number
        )

    def test_create_video_manager(self):
        """Test that a VideoManager can be created correctly"""
        self.assertEqual(self.video_manager.recording_info, self.recording_info)
        self.assertEqual(len(self.video_manager.video_recorders), len(self.camera_ids))
        self.assertFalse(self.video_manager.is_finished)

        # Check that all camera IDs are present in the video recorders
        for camera_id in self.camera_ids:
            self.assertIn(camera_id, self.video_manager.video_recorders)
            self.assertIsInstance(self.video_manager.video_recorders[camera_id], VideoRecorder)

        # Check that the camera_configs property returns the correct configs
        camera_configs = self.video_manager.camera_configs
        self.assertEqual(len(camera_configs), len(self.camera_ids))
        for camera_id in self.camera_ids:
            self.assertIn(camera_id, camera_configs)
            self.assertEqual(camera_configs[camera_id], self.camera_configs[camera_id])

    def test_add_multi_frame(self):
        """Test adding a multi-frame to the video manager"""
        multi_frame = self.create_multi_frame(1)
        self.video_manager.add_multi_frame(multi_frame)

        # Check that frames were added to each video recorder
        for camera_id in self.camera_ids:
            self.assertEqual(self.video_manager.video_recorders[camera_id].number_of_frames_to_write, 1)

        # Check that the frame was added to the recording timestamps
        self.assertEqual(len(self.video_manager.recording_timestamps.multiframe_timestamps), 1)

    def test_add_multi_frame_recarrays(self):
        """Test adding multi-frame recarrays to the video manager"""
        # Create a mock recarray that would be converted to a MultiFramePayload
        mock_recarray = MagicMock(spec=np.recarray)

        with patch.object(MultiFramePayload, 'from_numpy_record_array',
                          return_value=self.create_multi_frame(1)) as mock_from_recarray:
            self.video_manager.add_multi_frame_recarrays([mock_recarray])

            # Check that the recarray was added to the queue
            self.assertEqual(len(self.video_manager.mf_recarrays), 1)

            # Process the recarray
            result = self.video_manager.do_opportunistic_tasks()

            # Check that the method returned True (indicating work was done)
            self.assertTrue(result)

            # Check that the recarray was processed
            self.assertEqual(len(self.video_manager.mf_recarrays), 0)

            # Check that from_numpy_record_array was called
            mock_from_recarray.assert_called_once_with(mock_recarray, apply_config_rotation=True)

            # Check that frames were added to each video recorder
            for camera_id in self.camera_ids:
                self.assertEqual(self.video_manager.video_recorders[camera_id].number_of_frames_to_write, 1)

    def test_frame_counts_to_save(self):
        """Test the frame_counts_to_save property"""
        # Initially, no frames to save
        frame_counts = self.video_manager.frame_counts_to_save
        for camera_id in self.camera_ids:
            self.assertEqual(frame_counts[camera_id], 0)

        # Add a multi-frame
        multi_frame = self.create_multi_frame(1)
        self.video_manager.add_multi_frame(multi_frame)

        # Check that frame counts were updated
        frame_counts = self.video_manager.frame_counts_to_save
        for camera_id in self.camera_ids:
            self.assertEqual(frame_counts[camera_id], 1)

    def test_try_save_one_frame(self):
        """Test saving one frame"""
        # Add a multi-frame
        multi_frame = self.create_multi_frame(1)
        self.video_manager.add_multi_frame(multi_frame)

        # Save one frame
        result = self.video_manager.try_save_one_frame()

        # Check that the method returned True (indicating a frame was saved)
        self.assertTrue(result)

        # Check that one frame was saved from one camera
        total_frames_left = sum(self.video_manager.frame_counts_to_save.values())
        self.assertEqual(total_frames_left, len(self.camera_ids) - 1)

        # Save remaining frames
        while self.video_manager.try_save_one_frame():
            pass

        # Check that all frames were saved
        for camera_id in self.camera_ids:
            self.assertEqual(self.video_manager.frame_counts_to_save[camera_id], 0)

    def test_do_opportunistic_tasks(self):
        """Test the do_opportunistic_tasks method"""
        # Add a multi-frame recarray
        mock_recarray = MagicMock(spec=np.recarray)

        with patch.object(MultiFramePayload, 'from_numpy_record_array', return_value=self.create_multi_frame(1)):
            self.video_manager.add_multi_frame_recarrays([mock_recarray])

            # Process the recarray
            result = self.video_manager.do_opportunistic_tasks()

            # Check that the method returned True (indicating work was done)
            self.assertTrue(result)

            # Check that the recarray was processed
            self.assertEqual(len(self.video_manager.mf_recarrays), 0)

            # Add a multi-frame directly
            multi_frame = self.create_multi_frame(2)
            self.video_manager.add_multi_frame(multi_frame)

            # Process a frame
            result = self.video_manager.do_opportunistic_tasks()

            # Check that the method returned True (indicating work was done)
            self.assertTrue(result)

            # Process remaining frames
            while self.video_manager.do_opportunistic_tasks():
                pass

            # Check that all frames were processed
            for camera_id in self.camera_ids:
                self.assertEqual(self.video_manager.frame_counts_to_save[camera_id], 0)

    # def test_finish_and_close(self):
    #     """Test finishing and closing the video manager"""
    #     # Add some multi-frames
    #     for i in range(1, 4):
    #         multi_frame = self.create_multi_frame(i)
    #         self.video_manager.add_multi_frame(multi_frame)
    #
    #     # Add a recarray
    #     mock_recarray = MagicMock(spec=np.recarray)
    #     with patch.object(MultiFramePayload, 'from_numpy_record_array', return_value=self.create_multi_frame(4)):
    #         self.video_manager.add_multi_frame_recarrays([mock_recarray])
    #
    #         # Finish and close
    #         self.video_manager.finish_and_close()
    #
    #     # Check that all frames were processed
    #     for camera_id in self.camera_ids:
    #         self.assertEqual(self.video_manager.frame_counts_to_save[camera_id], 0)
    #
    #     # Check that the video manager is marked as finished
    #     self.assertTrue(self.video_manager.is_finished)
    #
    #     # Check that the recording info was saved
    #     self.assertTrue(Path(self.recording_info.recording_info_path).exists())
    #
    #     # Check that the timestamps were saved
    #     self.assertTrue(Path(self.recording_info.timestamps_file_path).exists())
    #
    #     # Check that the README file was created
    #     readme_path = Path(self.recording_info.videos_folder) / SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME
    #     self.assertTrue(readme_path.exists())

    # def test_close_with_frames(self):
    #     """Test closing the video manager with frames"""
    #     # Add a multi-frame
    #     multi_frame = self.create_multi_frame(1)
    #     self.video_manager.add_multi_frame(multi_frame)
    #
    #     # With only one frame, we can't calculate framerate statistics
    #     # So closing should raise a ValueError
    #     with self.assertRaises(ValueError) as context:
    #         self.video_manager.close()
    #
    #     self.assertIn("Cannot calculate framerate statistics with fewer than 2 frames", str(context.exception))
    #
    #     # Add another frame so we can calculate framerate
    #     multi_frame2 = self.create_multi_frame(2)
    #     self.video_manager.add_multi_frame(multi_frame2)
    #     multi_frame3 = self.create_multi_frame(3)
    #     self.video_manager.add_multi_frame(multi_frame3)
    #     multi_frame4 = self.create_multi_frame(4)
    #     self.video_manager.add_multi_frame(multi_frame4)
    #
    #     # Now closing should work
    #     self.video_manager.finish_and_close()
    #
    #     # Check that all video recorders were closed
    #     for camera_id in self.camera_ids:
    #         self.assertIsNone(self.video_manager.video_recorders[camera_id].video_writer)
    #
    #     # Check that the video manager is marked as finished
    #     self.assertTrue(self.video_manager.is_finished)
    #
    #     # Check that the recording info was saved
    #     self.assertTrue(Path(self.recording_info.recording_info_path).exists())
    #
    #     # Check that the timestamps were saved
    #     self.assertTrue(Path(self.recording_info.timestamps_folder).exists())
    # def test_finalize_recording_with_frames(self):
    #     """Test finalizing the recording with frames"""
    #     # Add a multi-frame
    #     multi_frame = self.create_multi_frame(1)
    #     self.video_manager.add_multi_frame(multi_frame)
    #
    #     # Process the frame to ensure we have timestamps
    #     self.video_manager.try_save_one_frame()
    #
    #     # Finalize the recording
    #     self.video_manager.finalize_recording()
    #
    #     # Check that the recording info was saved
    #     self.assertTrue(Path(self.recording_info.recording_info_path).exists())
    #
    #     # Check that the timestamps were saved
    #     self.assertTrue(Path(self.recording_info.timestamps_file_path).exists())
    #
    #     # Check that the README file was created
    #     readme_path = Path(self.recording_info.videos_folder) / SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME
    #     self.assertTrue(readme_path.exists())
    #
    #     # Check that the video manager is marked as finished
    #     self.assertTrue(self.video_manager.is_finished)

    def test_empty_manager_save_frame(self):
        """Test behavior with an empty manager (no frames) when trying to save a frame"""
        # Try to save a frame when no frames are available
        result = self.video_manager.try_save_one_frame()

        # Should return False
        self.assertFalse(result)

    def test_empty_manager_finish(self):
        """Test behavior with an empty manager (no frames) when finishing"""
        # This should raise a ValueError because there are no timestamps to save
        with self.assertRaises(ValueError) as context:
            self.video_manager.finish_and_close()

        self.assertIn("No multiframe timestamps available to save", str(context.exception))

    def test_already_finished(self):
        """Test behavior when the manager is already finished"""
        # Mark the manager as finished
        self.video_manager.is_finished = True

        # Add a multi-frame
        multi_frame = self.create_multi_frame(1)
        self.video_manager.add_multi_frame(multi_frame)

        # Try to save a frame
        result = self.video_manager.try_save_one_frame()

        # Should return False
        self.assertFalse(result)

        # Frames should still be in the recorders
        for camera_id in self.camera_ids:
            self.assertEqual(self.video_manager.video_recorders[camera_id].number_of_frames_to_write, 1)