from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.timestamps.frame_timestamps import FrameTimestamps
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE, CAMERA_CONFIG_DTYPE


class TestFrameMetadata:
    @pytest.fixture
    def camera_config(self):
        # Create a more complete mock CameraConfig with all required attributes
        config = MagicMock(spec=CameraConfig)
        config.camera_id = "test_camera"
        config.camera_name = "Test Camera"  # Add this missing attribute
        config.camera_index = 0
        config.use_this_camera = True
        config.resolution = MagicMock()
        config.resolution.height = 720
        config.resolution.width = 1280
        config.color_channels = 3
        config.pixel_format = "RGB"
        config.exposure_mode = "MANUAL"
        config.exposure = -7
        config.framerate = 30.0
        config.rotation = MagicMock()
        config.rotation.value = "NO_ROTATION"
        config.capture_fourcc = "MJPG"
        config.writer_fourcc = "X264"

        # Create a proper record array for the mock's to_numpy_record_array method
        mock_rec_array = np.recarray(1, dtype=CAMERA_CONFIG_DTYPE)
        mock_rec_array.camera_id[0] = config.camera_id
        mock_rec_array.camera_index[0] = config.camera_index
        mock_rec_array.camera_name[0] = config.camera_name
        mock_rec_array.use_this_camera[0] = config.use_this_camera
        mock_rec_array.resolution_height[0] = config.resolution.height
        mock_rec_array.resolution_width[0] = config.resolution.width
        mock_rec_array.color_channels[0] = config.color_channels
        mock_rec_array.pixel_format[0] = config.pixel_format
        mock_rec_array.exposure_mode[0] = config.exposure_mode
        mock_rec_array.exposure[0] = config.exposure
        mock_rec_array.framerate[0] = config.framerate
        mock_rec_array.rotation[0] = config.rotation.value
        mock_rec_array.capture_fourcc[0] = config.capture_fourcc
        mock_rec_array.writer_fourcc[0] = config.writer_fourcc

        config.to_numpy_record_array.return_value = mock_rec_array
        return config

    @pytest.fixture
    def timebase_mapping(self):
        return TimebaseMapping()

    @pytest.fixture
    def frame_timestamps(self, timebase_mapping):
        timestamps = FrameTimestamps(timebase_mapping=timebase_mapping)
        timestamps.pre_frame_grab_ns = 1000
        timestamps.post_frame_grab_ns = 2000
        return timestamps

    def test_frame_metadata_initialization(self, camera_config, frame_timestamps):
        """Test that FrameMetadata initializes correctly."""
        metadata = FrameMetadata(
            frame_number=42,
            camera_config=camera_config,
            timestamps=frame_timestamps
        )

        assert metadata.frame_number == 42
        assert metadata.camera_config == camera_config
        assert metadata.timestamps == frame_timestamps
        assert metadata.camera_id == "test_camera"

    # def test_initialize_frame_metadata_rec_array(self, camera_config, timebase_mapping):
    #     """Test that initialize_frame_metadata_rec_array creates a valid record array."""
    #     frame_number = 42
    #
    #     rec_array = initialize_frame_metadata_rec_array(
    #         camera_config=camera_config,
    #         frame_number=frame_number,
    #         timebase_mapping=timebase_mapping
    #     )
    #
    #     assert isinstance(rec_array, np.recarray)
    #     assert rec_array.shape == (1,)
    #     assert rec_array.dtype == FRAME_METADATA_DTYPE
    #     assert rec_array.frame_number[0] == frame_number

    def test_to_numpy_record_array(self, camera_config, frame_timestamps):
        """Test conversion to numpy record array."""
        metadata = FrameMetadata(
            frame_number=42,
            camera_config=camera_config,
            timestamps=frame_timestamps
        )

        rec_array = metadata.to_numpy_record_array()

        assert isinstance(rec_array, np.recarray)
        assert rec_array.shape == (1,)
        assert rec_array.dtype == FRAME_METADATA_DTYPE
        assert rec_array.frame_number[0] == 42

    # def test_from_numpy_record_array(self, camera_config, timebase_mapping):
    #     """Test creation from numpy record array."""
    #     frame_number = 42
    #
    #     # Create a record array
    #     rec_array = initialize_frame_metadata_rec_array(
    #         camera_config=camera_config,
    #         frame_number=frame_number,
    #         timebase_mapping=timebase_mapping
    #     )
    #
    #     # Mock the from_numpy_record_array methods that would be called
    #     with patch.object(CameraConfig, 'from_numpy_record_array', return_value=camera_config):
    #         with patch.object(FrameTimestamps, 'from_numpy_record_array',
    #                           return_value=FrameTimestamps(timebase_mapping=timebase_mapping)):
    #             # Convert back to FrameMetadata
    #             metadata = FrameMetadata.from_numpy_record_array(rec_array)
    #
    #             assert metadata.frame_number == frame_number
    #             assert metadata.camera_config == camera_config
    #             CameraConfig.from_numpy_record_array.assert_called_once()
    #             FrameTimestamps.from_numpy_record_array.assert_called_once()

    def test_validation_error_on_wrong_dtype(self):
        """Test that an error is raised when trying to create from an array with wrong dtype."""
        wrong_dtype = np.dtype([('wrong_field', np.int32)])
        wrong_array = np.recarray(1, dtype=wrong_dtype)

        with pytest.raises(ValueError):
            FrameMetadata.from_numpy_record_array(wrong_array)