"""Extended tests for CameraConfig — validation, orientation, serialization edge cases."""
import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import (
    CameraConfig,
    CameraConfigs,
    OrientationTypes,
    RotationTypes,
    validate_camera_configs,
    get_video_file_type,
    DEFAULT_CAMERA_ID,
    DEFAULT_IMAGE_HEIGHT,
    DEFAULT_IMAGE_WIDTH,
)
from skellycam.core.camera.config.image_resolution import ImageResolution


# ---------------------------------------------------------------------------
# validate_camera_configs
# ---------------------------------------------------------------------------

class TestValidateCameraConfigs:
    def test_valid_configs_pass(self) -> None:
        configs: CameraConfigs = {
            "cam0": CameraConfig(camera_id="cam0", camera_index=0),
            "cam1": CameraConfig(camera_id="cam1", camera_index=1),
        }
        validate_camera_configs(configs)  # should not raise

    def test_non_dict_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="dictionary"):
            validate_camera_configs([CameraConfig()])  # type: ignore[arg-type]

    def test_non_camera_config_value_raises(self) -> None:
        with pytest.raises(TypeError, match="CameraConfig"):
            validate_camera_configs({"cam0": {"not": "a config"}})  # type: ignore[dict-item]

    def test_mismatched_camera_id_raises(self) -> None:
        config = CameraConfig(camera_id="cam0", camera_index=0)
        with pytest.raises(ValueError, match="mismatch"):
            validate_camera_configs({"wrong_key": config})

    def test_duplicate_camera_indexes_raises(self) -> None:
        configs: CameraConfigs = {
            "cam0": CameraConfig(camera_id="cam0", camera_index=0),
            "cam1": CameraConfig(camera_id="cam1", camera_index=0),  # same index!
        }
        with pytest.raises(ValueError, match="unique"):
            validate_camera_configs(configs)


# ---------------------------------------------------------------------------
# Orientation and Image Shape
# ---------------------------------------------------------------------------

class TestCameraConfigOrientation:
    def test_landscape_no_rotation(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=720, width=1280),
            rotation=RotationTypes.NO_ROTATION,
        )
        assert config.orientation == OrientationTypes.LANDSCAPE
        assert config.image_shape == (720, 1280, 3)
        assert config.width == 1280
        assert config.height == 720

    def test_portrait_90_clockwise(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=720, width=1280),
            rotation=RotationTypes.CLOCKWISE_90,
        )
        assert config.orientation == OrientationTypes.PORTRAIT
        # In portrait, width/height swap in image_shape
        assert config.image_shape == (1280, 720, 3)
        assert config.width == 720
        assert config.height == 1280

    def test_landscape_180_rotation(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=720, width=1280),
            rotation=RotationTypes.ROTATE_180,
        )
        assert config.orientation == OrientationTypes.LANDSCAPE

    def test_square_resolution(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=640, width=640),
        )
        assert config.orientation == OrientationTypes.SQUARE

    def test_monochrome_image_shape(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=480, width=640),
            color_channels=1,
        )
        # Monochrome: no channels dimension
        assert config.image_shape == (480, 640)

    def test_video_image_shape_is_width_height(self) -> None:
        """video_image_shape uses OpenCV convention (width, height)."""
        config = CameraConfig(
            resolution=ImageResolution(height=480, width=640),
        )
        assert config.video_image_shape == (640, 480)


# ---------------------------------------------------------------------------
# Numpy Record Array Roundtrip — Edge Cases
# ---------------------------------------------------------------------------

class TestNumpyRoundtripEdgeCases:
    def test_roundtrip_with_rotation(self) -> None:
        config = CameraConfig(
            camera_id="rotated",
            camera_index=2,
            rotation=RotationTypes.COUNTERCLOCKWISE_90,
        )
        arr = config.to_numpy_record_array()
        restored = CameraConfig.from_numpy_record_array(arr)
        assert restored.rotation == RotationTypes.COUNTERCLOCKWISE_90
        assert restored.camera_id == "rotated"

    def test_roundtrip_with_custom_resolution(self) -> None:
        config = CameraConfig(
            camera_id="hires",
            camera_index=0,
            resolution=ImageResolution(height=1080, width=1920),
        )
        arr = config.to_numpy_record_array()
        restored = CameraConfig.from_numpy_record_array(arr)
        assert restored.resolution.width == 1920
        assert restored.resolution.height == 1080

    def test_wrong_dtype_raises(self) -> None:
        bad_arr = np.recarray((1,), dtype=np.dtype([("garbage", np.int32)]))
        with pytest.raises(ValueError, match="mismatch"):
            CameraConfig.from_numpy_record_array(bad_arr)

    def test_roundtrip_preserves_framerate(self) -> None:
        config = CameraConfig(camera_id="fps_test", camera_index=0, framerate=29.97)
        arr = config.to_numpy_record_array()
        restored = CameraConfig.from_numpy_record_array(arr)
        assert abs(restored.framerate - 29.97) < 0.01


# ---------------------------------------------------------------------------
# Image Size Calculation
# ---------------------------------------------------------------------------

class TestImageSizeBytes:
    def test_default_image_size(self) -> None:
        config = CameraConfig()
        expected = DEFAULT_IMAGE_HEIGHT * DEFAULT_IMAGE_WIDTH * 3 * 1  # uint8
        assert config.image_size_bytes == expected

    def test_monochrome_image_size(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=100, width=100),
            color_channels=1,
        )
        assert config.image_size_bytes == 100 * 100 * 1


# ---------------------------------------------------------------------------
# get_video_file_type
# ---------------------------------------------------------------------------

class TestGetVideoFileType:
    def test_known_fourcc_codes(self) -> None:
        import cv2
        assert get_video_file_type(cv2.VideoWriter.fourcc(*"H264")) == "mp4"
        assert get_video_file_type(cv2.VideoWriter.fourcc(*"X264")) == "mp4"
        assert get_video_file_type(cv2.VideoWriter.fourcc(*"XVID")) == "avi"

    def test_unknown_fourcc_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized"):
            get_video_file_type(999999999)


# ---------------------------------------------------------------------------
# ImageResolution
# ---------------------------------------------------------------------------

class TestImageResolution:
    def test_from_string(self) -> None:
        res = ImageResolution.from_string("720x1280")
        assert res.height == 720
        assert res.width == 1280

    def test_aspect_ratio(self) -> None:
        res = ImageResolution(height=1080, width=1920)
        assert abs(res.aspect_ratio - (1920 / 1080)) < 1e-6

    def test_ordering(self) -> None:
        small = ImageResolution(height=480, width=640)
        large = ImageResolution(height=1080, width=1920)
        assert small < large
        assert not large < small

    def test_equality(self) -> None:
        a = ImageResolution(height=720, width=1280)
        b = ImageResolution(height=720, width=1280)
        assert a == b

    def test_hash_consistency(self) -> None:
        a = ImageResolution(height=720, width=1280)
        b = ImageResolution(height=720, width=1280)
        assert hash(a) == hash(b)

    def test_str(self) -> None:
        res = ImageResolution(height=720, width=1280)
        assert str(res) == "(720x1280)"
