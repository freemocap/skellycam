"""Tests for CameraConfig model logic."""
import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import (
    CameraConfig,
    DEFAULT_CAMERA_ID,
    RotationTypes,
)


class TestCameraConfigDefaults:
    def test_default_values(self):
        """CameraConfig() initializes with expected defaults."""
        config = CameraConfig()
        assert config.camera_id == DEFAULT_CAMERA_ID
        assert config.rotation == RotationTypes.NO_ROTATION

    def test_image_shape_default(self):
        """Default image shape is (height, width, channels)."""
        config = CameraConfig()
        shape = config.image_shape
        # Should be a tuple of (height, width, channels)
        assert len(shape) == 3
        assert shape[2] == 3  # BGR channels


class TestCameraConfigEquality:
    def test_identical_configs_are_equal(self):
        """Two default configs should be equal."""
        a = CameraConfig()
        b = CameraConfig()
        assert a == b

    def test_different_configs_are_not_equal(self):
        """Configs with different exposure should not be equal."""
        a = CameraConfig(exposure=-5)
        b = CameraConfig(exposure=-8)
        assert a != b

    def test_config_difference(self):
        """Subtraction of configs returns parameter differences."""
        a = CameraConfig(exposure=-5)
        b = CameraConfig(exposure=-8)
        diffs = a - b
        assert len(diffs) > 0
        exposure_diffs = [d for d in diffs if d.parameter_name == "exposure"]
        assert len(exposure_diffs) == 1


class TestSettableParameters:
    def test_roundtrip(self):
        """to_settable_parameters -> accept_settable_parameters preserves values."""
        original = CameraConfig(exposure=-7)
        params = original.to_settable_parameters()
        restored = CameraConfig()
        restored.accept_settable_parameters(params)
        assert original.exposure == restored.exposure


class TestNumpySerialization:
    def test_to_frame_camera_info(self):
        """to_frame_camera_info produces a recarray with the expected fields."""
        config = CameraConfig()
        info = config.to_frame_camera_info()
        assert isinstance(info, np.recarray)
        assert str(info.camera_id[0]) == config.camera_id
        assert int(info.camera_index[0]) == config.camera_index
        assert int(info.rotation[0]) == config.rotation.value
        assert int(info.color_channels[0]) == config.color_channels


class TestCameraConfigStr:
    def test_str_representation(self):
        """__str__ returns a non-empty string."""
        config = CameraConfig()
        s = str(config)
        assert len(s) > 0
        assert DEFAULT_CAMERA_ID in s
