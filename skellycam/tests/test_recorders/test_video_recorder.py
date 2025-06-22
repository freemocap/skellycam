import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

import cv2
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
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.timestamps.full_timestamp import FullTimestamp
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.image_rotation_types import RotationTypes
from skellycam.core.types.type_overloads import CameraIdString, CameraIndex


class TestVideoRecorder(TestCase):
    def setUp(self):
        # Create a temporary directory for test videos
        self.temp_dir = tempfile.mkdtemp()

        # Create a basic camera config
        self.camera_id = CameraIdString("test_camera")
        self.camera_index = CameraIndex(0)
        self.camera_config = CameraConfig(
            camera_id=self.camera_id,
            camera_index=self.camera_index,
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

        # Create a video recorder
        self.video_recorder = VideoRecorder.create(
            camera_id=self.camera_id,
            recording_info=self.recording_info,
            config=self.camera_config
        )

    def tearDown(self):
        # Clean up the temporary directory
        if hasattr(self, 'video_recorder') and self.video_recorder.video_writer is not None:
            self.video_recorder.close()

        shutil.rmtree(self.temp_dir)

    def create_test_frame(self, frame_number: int, color: tuple = (255, 0, 0)) -> FramePayload:
        """Helper method to create a test frame with specified number and color"""
        height, width = self.camera_config.resolution.height, self.camera_config.resolution.width
        channels = self.camera_config.color_channels

        # Create a colored image
        image = np.zeros((height, width, channels), dtype=np.uint8)
        if channels == 3:
            # For RGB images
            image[:, :] = color
        else:
            # For grayscale images
            image[:, :] = color[0]

        # Add frame number as text in the center of the image
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = f"Frame {frame_number}"
        text_size = cv2.getTextSize(text, font, 1, 2)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        cv2.putText(image, text, (text_x, text_y), font, 1, (255, 255, 255), 2)

        # Create frame metadata
        frame_metadata = FrameMetadata(
            frame_number=frame_number,
            camera_config=self.camera_config,
            timestamps=FrameTimestamps(timebase_mapping=self.timebase_mapping)
        )

        # Set timestamps to simulate a real frame
        frame_metadata.timestamps.pre_frame_grab_ns = self.timebase_mapping.perf_counter_ns
        frame_metadata.timestamps.post_frame_grab_ns = self.timebase_mapping.perf_counter_ns + 10000  # 10 microseconds later

        return FramePayload(image=image, frame_metadata=frame_metadata)

    def test_create_video_recorder(self):
        """Test that a VideoRecorder can be created correctly"""
        self.assertEqual(self.video_recorder.camera_id, self.camera_id)
        self.assertEqual(self.video_recorder.camera_config, self.camera_config)
        self.assertIsNone(self.video_recorder.video_writer)
        self.assertEqual(self.video_recorder.number_of_frames_to_write, 0)

        # Check that the video path is correct
        expected_path = str(Path(self.recording_info.videos_folder) /
                            f"{self.recording_info.recording_name}.camera{self.camera_config.camera_index}.{self.camera_config.camera_id}.{self.camera_config.video_file_extension}")
        self.assertEqual(self.video_recorder.video_file_path, expected_path)

        # Check that the directory exists
        self.assertTrue(Path(self.video_recorder.video_file_path).parent.exists())

    def test_add_frame(self):
        """Test adding a frame to the video recorder"""
        test_frame = self.create_test_frame(1)
        self.video_recorder.add_frame(test_frame)

        self.assertEqual(self.video_recorder.number_of_frames_to_write, 1)
        self.assertEqual(self.video_recorder.frames_to_write[0], test_frame)

    def test_write_one_frame(self):
        """Test writing a single frame to the video file"""
        test_frame = self.create_test_frame(1)
        self.video_recorder.add_frame(test_frame)

        # Write the frame
        frame_number = self.video_recorder.write_one_frame()

        # Check that the frame was written
        self.assertEqual(frame_number, 1)
        self.assertEqual(self.video_recorder.number_of_frames_to_write, 0)
        self.assertEqual(self.video_recorder.previous_frame, test_frame)

        # Check that the video writer was initialized
        self.assertIsNotNone(self.video_recorder.video_writer)
        self.assertTrue(self.video_recorder.video_writer.isOpened())

        # Check that the video file exists
        self.assertTrue(Path(self.video_recorder.video_file_path).exists())

    def test_write_multiple_frames(self):
        """Test writing multiple consecutive frames"""
        # Add 5 frames
        for i in range(1, 6):
            test_frame = self.create_test_frame(i, color=(50 * i, 0, 255 - 50 * i))
            self.video_recorder.add_frame(test_frame)

        # Check that all frames were added
        self.assertEqual(self.video_recorder.number_of_frames_to_write, 5)

        # Write all frames one by one
        for i in range(1, 6):
            frame_number = self.video_recorder.write_one_frame()
            self.assertEqual(frame_number, i)

        # Check that all frames were written
        self.assertEqual(self.video_recorder.number_of_frames_to_write, 0)
        self.assertEqual(self.video_recorder.previous_frame.frame_number, 5)

    def test_finish_and_close(self):
        """Test finishing and closing the video recorder"""
        # Add 3 frames
        for i in range(1, 4):
            test_frame = self.create_test_frame(i)
            self.video_recorder.add_frame(test_frame)

        # Finish and close
        self.video_recorder.finish_and_close()

        # Check that all frames were written
        self.assertEqual(self.video_recorder.number_of_frames_to_write, 0)

        # Check that the video writer was closed
        self.assertIsNotNone(self.video_recorder.video_writer)

        # Check that the video file exists and has content
        video_path = Path(self.video_recorder.video_file_path)
        self.assertTrue(video_path.exists())
        self.assertGreater(video_path.stat().st_size, 0)

    def test_non_consecutive_frame_numbers(self):
        """Test that an error is raised when frame numbers are not consecutive"""
        # Add frame 1
        frame1 = self.create_test_frame(1)
        self.video_recorder.add_frame(frame1)
        self.video_recorder.write_one_frame()

        # Add frame 3 (skipping 2)
        frame3 = self.create_test_frame(3)
        self.video_recorder.add_frame(frame3)

        # This should raise a ValueError
        with self.assertRaises(ValueError) as context:
            self.video_recorder.write_one_frame()

        self.assertIn("Frame numbers for camera", str(context.exception))
        self.assertIn("are not consecutive", str(context.exception))

    def test_different_resolutions(self):
        """Test with different resolutions"""
        # Create a camera config with a different resolution
        hd_resolution = ImageResolution(width=1920, height=1080)
        hd_camera_config = CameraConfig(
            camera_id=self.camera_id,
            camera_index=self.camera_index,
            resolution=hd_resolution,
            exposure_mode=DEFAULT_EXPOSURE_MODE,
            exposure=DEFAULT_EXPOSURE,
            framerate=DEFAULT_FRAMERATE,
            rotation=DEFAULT_ROTATION,
            capture_fourcc=DEFAULT_CAPTURE_FOURCC,
            writer_fourcc=DEFAULT_WRITER_FOURCC
        )

        # Create a new video recorder with the HD config
        hd_recorder = VideoRecorder.create(
            camera_id=self.camera_id,
            recording_info=self.recording_info,
            config=hd_camera_config
        )

        # Create and add a frame with the HD resolution
        height, width = hd_resolution.height, hd_resolution.width
        channels = hd_camera_config.color_channels

        image = np.zeros((height, width, channels), dtype=np.uint8)
        image[:, :] = (0, 255, 0)  # Green

        frame_metadata = FrameMetadata(
            frame_number=1,
            camera_config=hd_camera_config,
            timestamps=FrameTimestamps(timebase_mapping=self.timebase_mapping)
        )

        frame_metadata.timestamps.pre_frame_grab_ns = self.timebase_mapping.perf_counter_ns
        frame_metadata.timestamps.post_frame_grab_ns = self.timebase_mapping.perf_counter_ns + 10000

        hd_frame = FramePayload(image=image, frame_metadata=frame_metadata)

        # Add and write the frame
        hd_recorder.add_frame(hd_frame)
        hd_recorder.write_one_frame()

        # Close the recorder
        hd_recorder.close()

        # Check that the video file exists and has content
        video_path = Path(hd_recorder.video_file_path)
        self.assertTrue(video_path.exists())
        self.assertGreater(video_path.stat().st_size, 0)

        # Open the video file and check its properties
        cap = cv2.VideoCapture(str(video_path))
        self.assertTrue(cap.isOpened())

        # Check the video properties
        self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), width)
        self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), height)

        # Clean up
        cap.release()

    def test_different_rotations(self):
        """Test with different rotation settings"""
        # Create configs with different rotations
        rotations = [
            RotationTypes.NO_ROTATION,
            RotationTypes.COUNTERCLOCKWISE_90,
            RotationTypes.ROTATE_180,
            RotationTypes.CLOCKWISE_90
        ]

        for rotation in rotations:
            # Create a camera config with this rotation
            rotated_config = CameraConfig(
                camera_id=f"rotated_{rotation.name}",
                camera_index=self.camera_index,
                resolution=DEFAULT_RESOLUTION,
                exposure_mode=DEFAULT_EXPOSURE_MODE,
                exposure=DEFAULT_EXPOSURE,
                framerate=DEFAULT_FRAMERATE,
                rotation=rotation,
                capture_fourcc=DEFAULT_CAPTURE_FOURCC,
                writer_fourcc=DEFAULT_WRITER_FOURCC
            )

            # Create a video recorder with this config
            rotated_recorder = VideoRecorder.create(
                camera_id=rotated_config.camera_id,
                recording_info=self.recording_info,
                config=rotated_config
            )

            # Create a frame with this config
            frame_metadata = FrameMetadata(
                frame_number=1,
                camera_config=rotated_config,
                timestamps=FrameTimestamps(timebase_mapping=self.timebase_mapping)
            )

            frame_metadata.timestamps.pre_frame_grab_ns = self.timebase_mapping.perf_counter_ns
            frame_metadata.timestamps.post_frame_grab_ns = self.timebase_mapping.perf_counter_ns + 10000

            # Create a test pattern image
            height, width = rotated_config.resolution.height, rotated_config.resolution.width
            channels = rotated_config.color_channels

            image = np.zeros((height, width, channels), dtype=np.uint8)

            # Draw a pattern that makes rotation visible
            cv2.rectangle(image, (width // 4, height // 4), (3 * width // 4, 3 * height // 4), (0, 255, 0), 2)
            cv2.line(image, (width // 2, 0), (width // 2, height), (255, 0, 0), 2)
            cv2.line(image, (0, height // 2), (width, height // 2), (0, 0, 255), 2)

            # Add text indicating the rotation
            cv2.putText(image, f"Rotation: {rotation.name}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            rotated_frame = FramePayload(image=image, frame_metadata=frame_metadata)

            # Add and write the frame
            rotated_recorder.add_frame(rotated_frame)
            rotated_recorder.write_one_frame()

            # Close the recorder
            rotated_recorder.close()

            # Check that the video file exists
            video_path = Path(rotated_recorder.video_file_path)
            self.assertTrue(video_path.exists())
            self.assertGreater(video_path.stat().st_size, 0)

    def test_different_codecs(self):
        """Test with different video codecs"""
        # Test with different writer_fourcc values
        codecs = ["XVID", "MJPG"]  # These should be widely available

        for codec in codecs:
            # Create a camera config with this codec
            codec_config = CameraConfig(
                camera_id=f"codec_{codec}",
                camera_index=self.camera_index,
                resolution=DEFAULT_RESOLUTION,
                exposure_mode=DEFAULT_EXPOSURE_MODE,
                exposure=DEFAULT_EXPOSURE,
                framerate=DEFAULT_FRAMERATE,
                rotation=DEFAULT_ROTATION,
                capture_fourcc=DEFAULT_CAPTURE_FOURCC,
                writer_fourcc=codec
            )

            # Create a video recorder with this config
            codec_recorder = VideoRecorder.create(
                camera_id=codec_config.camera_id,
                recording_info=self.recording_info,
                config=codec_config
            )

            # Create a test frame
            test_frame = self.create_test_frame(1)
            # Update the frame's camera_config to match our codec config
            test_frame.frame_metadata.camera_config = codec_config

            # Add and write the frame
            codec_recorder.add_frame(test_frame)
            codec_recorder.write_one_frame()

            # Close the recorder
            codec_recorder.close()

            # Check that the video file exists
            video_path = Path(codec_recorder.video_file_path)
            self.assertTrue(video_path.exists())
            self.assertGreater(video_path.stat().st_size, 0)

    # def test_grayscale_video(self):
    #     """Test recording grayscale video"""
    #     # Create a camera config for grayscale
    #     grayscale_config = CameraConfig(
    #         camera_id="grayscale",
    #         camera_index=self.camera_index,
    #         resolution=DEFAULT_RESOLUTION,
    #         exposure_mode=DEFAULT_EXPOSURE_MODE,
    #         exposure=DEFAULT_EXPOSURE,
    #         framerate=DEFAULT_FRAMERATE,
    #         rotation=DEFAULT_ROTATION,
    #         capture_fourcc=DEFAULT_CAPTURE_FOURCC,
    #         writer_fourcc=DEFAULT_WRITER_FOURCC,
    #         color_channels=1  # Grayscale
    #     )
    #
    #     # Create a video recorder with this config
    #     grayscale_recorder = VideoRecorder.create(
    #         camera_id=grayscale_config.camera_id,
    #         recording_info=self.recording_info,
    #         config=grayscale_config
    #     )
    #
    #     # Create a grayscale frame
    #     height, width = grayscale_config.resolution.height, grayscale_config.resolution.width
    #
    #     # Create a grayscale test pattern
    #     image = np.zeros((height, width), dtype=np.uint8)
    #
    #     # Create a gradient pattern
    #     for i in range(height):
    #         image[i, :] = int(255 * i / height)
    #
    #     # Add text
    #     cv2.putText(image, "Grayscale Test", (width // 4, height // 2),
    #                 cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)
    #
    #     frame_metadata = FrameMetadata(
    #         frame_number=1,
    #         camera_config=grayscale_config,
    #         timestamps=FrameTimestamps(timebase_mapping=self.timebase_mapping)
    #     )
    #
    #     frame_metadata.timestamps.pre_frame_grab_ns = self.timebase_mapping.perf_counter_ns
    #     frame_metadata.timestamps.post_frame_grab_ns = self.timebase_mapping.perf_counter_ns + 10000
    #
    #     grayscale_frame = FramePayload(image=image, frame_metadata=frame_metadata)
    #
    #     # Add and write the frame
    #     grayscale_recorder.add_frame(grayscale_frame)
    #     grayscale_recorder.write_one_frame()
    #
    #     # Close the recorder
    #     grayscale_recorder.close()
    #
    #     # Check that the video file exists
    #     video_path = Path(grayscale_recorder.video_file_path)
    #     self.assertTrue(video_path.exists())
    #     self.assertGreater(video_path.stat().st_size, 0)
    #
    #     # Open the video and check it's grayscale
    #     cap = cv2.VideoCapture(str(video_path))
    #     ret, frame = cap.read()
    #
    #     self.assertTrue(ret)
    #     # OpenCV might convert grayscale to BGR when reading
    #     if len(frame.shape) == 3:
    #         # Convert back to grayscale for comparison
    #         frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #
    #     self.assertEqual(len(frame.shape), 2)  # Should be 2D for grayscale
    #
    #     cap.release()

    def test_validate_frame_mismatch(self):
        """Test that validation fails when frame config doesn't match recorder config"""
        # Create a frame with a different config
        different_config = CameraConfig(
            camera_id=self.camera_id,
            camera_index=self.camera_index,
            resolution=ImageResolution(width=640, height=480),  # Different resolution
            exposure_mode=DEFAULT_EXPOSURE_MODE,
            exposure=DEFAULT_EXPOSURE,
            framerate=DEFAULT_FRAMERATE,
            rotation=DEFAULT_ROTATION,
            capture_fourcc=DEFAULT_CAPTURE_FOURCC,
            writer_fourcc=DEFAULT_WRITER_FOURCC
        )

        frame_metadata = FrameMetadata(
            frame_number=1,
            camera_config=different_config,
            timestamps=FrameTimestamps(timebase_mapping=self.timebase_mapping)
        )

        # Create an image with the different resolution
        image = np.zeros((480, 640, 3), dtype=np.uint8)

        mismatched_frame = FramePayload(image=image, frame_metadata=frame_metadata)

        # This should raise a ValueError when added
        with self.assertRaises(ValueError):
            self.video_recorder.add_frame(mismatched_frame)

    def test_empty_queue(self):
        """Test behavior when trying to write from an empty queue"""
        # Try to write when no frames are in the queue
        result = self.video_recorder.write_one_frame()

        # Should return None
        self.assertIsNone(result)

        # Video writer should not be initialized
        self.assertIsNone(self.video_recorder.video_writer)