"""Unit tests for ``_skellycam_rust`` PyO3 types (no hardware required).

These tests exercise every ``#[pyclass]`` exposed by the Rust PyO3 bridge.
They are fast, deterministic, and can run in CI without cameras.

Usage::

    uv run pytest skellycam/tests/test_rust_bridge_types.py -v
"""

import pytest

# ── Module-level import guard ──────────────────────────────────────────────────
_RUST_SKIP_REASON = ""

try:
    import _skellycam_rust

    assert hasattr(_skellycam_rust, "CameraGroupManager")
    assert hasattr(_skellycam_rust, "detect_cameras")
    _RUST_AVAILABLE = True
except (ImportError, AssertionError) as e:
    _RUST_AVAILABLE = False
    _RUST_SKIP_REASON = f"_skellycam_rust not available: {e}"

requires_rust = pytest.mark.skipif(
    not _RUST_AVAILABLE,
    reason=_RUST_SKIP_REASON,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ImageResolution
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestImageResolution:
    """Tests for the ``ImageResolution`` PyO3 class."""

    def test_default_construction(self) -> None:
        """Default constructor gives 1280x720."""
        res = _skellycam_rust.ImageResolution()
        assert res.height == 720
        assert res.width == 1280

    def test_custom_construction(self) -> None:
        """Explicit height and width are stored correctly."""
        res = _skellycam_rust.ImageResolution(height=480, width=640)
        assert res.height == 480
        assert res.width == 640

    def test_aspect_ratio(self) -> None:
        """Aspect ratio is width / height."""
        res = _skellycam_rust.ImageResolution(height=720, width=1280)
        assert res.aspect_ratio == pytest.approx(1280.0 / 720.0)

    def test_aspect_ratio_square(self) -> None:
        """Square resolution returns 1.0."""
        res = _skellycam_rust.ImageResolution(height=1080, width=1080)
        assert res.aspect_ratio == 1.0

    def test_as_tuple(self) -> None:
        """as_tuple() returns (width, height)."""
        res = _skellycam_rust.ImageResolution(height=480, width=640)
        assert res.as_tuple() == (640, 480)

    def test_model_dump(self) -> None:
        """model_dump() returns a dict with height and width."""
        res = _skellycam_rust.ImageResolution(height=720, width=1280)
        dumped = res.model_dump()
        assert dumped == {"height": 720, "width": 1280}

    def test_repr(self) -> None:
        """__repr__ includes class name and field values."""
        res = _skellycam_rust.ImageResolution(height=480, width=640)
        r = repr(res)
        assert "ImageResolution" in r
        assert "480" in r
        assert "640" in r

    def test_str(self) -> None:
        """__str__ gives (HxW) format."""
        res = _skellycam_rust.ImageResolution(height=720, width=1280)
        assert str(res) == "(720x1280)"


# ═══════════════════════════════════════════════════════════════════════════════
# CameraConfig
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestCameraConfig:
    """Tests for the ``CameraConfig`` PyO3 class."""

    def test_default_construction(self) -> None:
        """Default constructor produces expected defaults matching the OpenAPI schema."""
        cfg = _skellycam_rust.CameraConfig()
        assert cfg.camera_id == "000"
        assert cfg.camera_index == 0
        assert cfg.camera_name == "Default Camera"
        assert cfg.use_this_camera is True
        assert cfg.color_channels == 3
        assert cfg.pixel_format == "RGB"
        assert cfg.exposure_mode == "MANUAL"
        assert cfg.exposure == -7
        assert cfg.framerate == pytest.approx(-1.0)
        assert cfg.rotation == -1
        assert cfg.capture_fourcc == "MJPG"
        assert cfg.writer_fourcc == "X264"

        res = cfg.resolution
        assert res.height == 720
        assert res.width == 1280

    def test_custom_construction(self) -> None:
        """All 15 positional/keyword params are stored correctly."""
        cfg = _skellycam_rust.CameraConfig(
            camera_id="cam_01",
            camera_index=3,
            camera_name="TestCam",
            use_this_camera=False,
            height=480,
            width=640,
            color_channels=1,
            pixel_format="GRAY",
            exposure_mode="AUTO",
            exposure=-5,
            framerate=60.0,
            rotation=0,
            capture_fourcc="YUYV",
            writer_fourcc="H264",
        )
        assert cfg.camera_id == "cam_01"
        assert cfg.camera_index == 3
        assert cfg.camera_name == "TestCam"
        assert cfg.use_this_camera is False
        assert cfg.color_channels == 1
        assert cfg.pixel_format == "GRAY"
        assert cfg.exposure_mode == "AUTO"
        assert cfg.exposure == -5
        assert cfg.framerate == pytest.approx(60.0)
        assert cfg.rotation == 0
        assert cfg.capture_fourcc == "YUYV"
        assert cfg.writer_fourcc == "H264"
        assert cfg.resolution.height == 480
        assert cfg.resolution.width == 640

    def test_from_dict_constructs_correctly(self) -> None:
        """from_dict() static method parses a Python dict matching the HTTP request body."""
        data = {
            "camera_id": "abc",
            "camera_index": 2,
            "camera_name": "FromDict",
            "use_this_camera": False,
            "resolution": {"height": 600, "width": 800},
            "color_channels": 3,
            "pixel_format": "RGB",
            "exposure_mode": "AUTO",
            "exposure": -3,
            "framerate": 30.0,
            "rotation": 1,
            "capture_fourcc": "MJPG",
            "writer_fourcc": "X264",
        }
        cfg = _skellycam_rust.CameraConfig.from_dict(data)
        assert cfg.camera_id == "abc"
        assert cfg.camera_index == 2
        assert cfg.camera_name == "FromDict"
        assert cfg.use_this_camera is False
        assert cfg.resolution.height == 600
        assert cfg.resolution.width == 800
        assert cfg.exposure == -3
        assert cfg.framerate == pytest.approx(30.0)
        assert cfg.rotation == 1

    def test_from_dict_missing_fields_use_defaults(self) -> None:
        """from_dict() fills in defaults for absent keys."""
        cfg = _skellycam_rust.CameraConfig.from_dict({"camera_index": 0})
        assert cfg.camera_id == "000"
        assert cfg.camera_name == "Default Camera"
        assert cfg.exposure == -7
        assert cfg.framerate == pytest.approx(-1.0)
        assert cfg.resolution.height == 720
        assert cfg.resolution.width == 1280

    # ── Orientation ──────────────────────────────────────────────────────

    def test_orientation_landscape_no_rotation(self) -> None:
        """rotation=-1 (NoRotation) on non-square → LANDSCAPE."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280, rotation=-1)
        assert cfg.orientation == "LANDSCAPE"

    def test_orientation_landscape_rotate_180(self) -> None:
        """rotation=1 (Rotate180) on non-square → LANDSCAPE."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280, rotation=1)
        assert cfg.orientation == "LANDSCAPE"

    def test_orientation_portrait_clockwise_90(self) -> None:
        """rotation=0 (Clockwise90) on non-square → PORTRAIT."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280, rotation=0)
        assert cfg.orientation == "PORTRAIT"

    def test_orientation_portrait_counterclockwise_90(self) -> None:
        """rotation=2 (CounterClockwise90) on non-square → PORTRAIT."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280, rotation=2)
        assert cfg.orientation == "PORTRAIT"

    def test_orientation_square(self) -> None:
        """Square resolution always returns SQUARE regardless of rotation."""
        cfg = _skellycam_rust.CameraConfig(height=1080, width=1080, rotation=0)
        assert cfg.orientation == "SQUARE"

    # ── Width/height getters (rotation-aware) ────────────────────────────

    def test_width_height_landscape(self) -> None:
        """Landscape: width and height match resolution dimensions."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280, rotation=-1)
        assert cfg.width == 1280
        assert cfg.height == 720

    def test_width_height_portrait_swapped(self) -> None:
        """Portrait: width and height are swapped relative to resolution."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280, rotation=0)
        assert cfg.width == 720
        assert cfg.height == 1280

    # ── Computed properties ──────────────────────────────────────────────

    def test_image_shape_landscape(self) -> None:
        """image_shape is (height, width, channels) in landscape."""
        cfg = _skellycam_rust.CameraConfig(
            height=720, width=1280, color_channels=3, rotation=-1
        )
        assert cfg.image_shape == (720, 1280, 3)

    def test_image_shape_portrait(self) -> None:
        """image_shape swaps height/width in portrait."""
        cfg = _skellycam_rust.CameraConfig(
            height=720, width=1280, color_channels=3, rotation=0
        )
        assert cfg.image_shape == (1280, 720, 3)

    def test_video_image_shape(self) -> None:
        """video_image_shape is always (resolution.width, resolution.height)."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280)
        assert cfg.video_image_shape == (1280, 720)

    def test_image_size_bytes(self) -> None:
        """image_size_bytes = width * height * channels."""
        cfg = _skellycam_rust.CameraConfig(
            height=480, width=640, color_channels=3, rotation=-1
        )
        assert cfg.image_size_bytes == 640 * 480 * 3

    def test_aspect_ratio(self) -> None:
        """aspect_ratio delegates to ImageResolution.aspect_ratio."""
        cfg = _skellycam_rust.CameraConfig(height=720, width=1280)
        assert cfg.aspect_ratio == pytest.approx(1280.0 / 720.0)

    # ── Serialization ────────────────────────────────────────────────────

    def test_model_dump_includes_computed_fields(self) -> None:
        """model_dump() returns a dict with both stored and computed fields."""
        cfg = _skellycam_rust.CameraConfig(
            camera_id="cam_x",
            camera_index=1,
            camera_name="Test",
            height=480,
            width=640,
        )
        dumped = cfg.model_dump()
        assert dumped["camera_id"] == "cam_x"
        assert dumped["camera_index"] == 1
        assert dumped["camera_name"] == "Test"
        assert isinstance(dumped["resolution"], dict)
        assert dumped["resolution"]["height"] == 480
        assert dumped["orientation"] == "LANDSCAPE"
        assert "aspect_ratio" in dumped
        assert "width" in dumped
        assert "height" in dumped
        assert "image_shape" in dumped

    def test_model_dump_round_trip_via_from_dict(self) -> None:
        """model_dump() → from_dict() round-trip preserves key fields."""
        original = _skellycam_rust.CameraConfig(
            camera_id="roundtrip",
            camera_index=5,
            camera_name="RoundTrip",
            height=600,
            width=800,
            exposure=-8,
            framerate=30.0,
            rotation=0,
        )
        dumped = original.model_dump()
        # The dumped dict has extra computed keys; from_dict should ignore them
        reconstructed = _skellycam_rust.CameraConfig.from_dict(dumped)
        assert reconstructed.camera_id == original.camera_id
        assert reconstructed.camera_index == original.camera_index
        assert reconstructed.resolution.height == original.resolution.height
        assert reconstructed.resolution.width == original.resolution.width
        assert reconstructed.exposure == original.exposure
        assert reconstructed.rotation == original.rotation

    def test_repr(self) -> None:
        """__repr__ includes camera_id, camera_index, camera_name."""
        cfg = _skellycam_rust.CameraConfig(
            camera_id="abc", camera_index=2, camera_name="Foo"
        )
        r = repr(cfg)
        assert "CameraConfig" in r
        assert "abc" in r
        assert "Foo" in r


# ═══════════════════════════════════════════════════════════════════════════════
# RecordingInfo
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestRecordingInfo:
    """Tests for the ``RecordingInfo`` PyO3 class."""

    def test_construction_with_name_and_directory(self) -> None:
        """Minimal construction requires recording_name and recording_directory."""
        info = _skellycam_rust.RecordingInfo(
            "test_session", "/tmp/recordings"
        )
        assert info.recording_name == "test_session"
        assert info.recording_directory == "/tmp/recordings"
        # UUID should be auto-generated
        assert len(info.recording_uuid) == 36  # standard UUID format
        assert info.mic_device_index == -1

    def test_construction_with_explicit_uuid(self) -> None:
        """Explicit UUID is preserved."""
        info = _skellycam_rust.RecordingInfo(
            "session", "/tmp/recs", recording_uuid="deadbeef-dead-beef-dead-beefdeadbeef"
        )
        assert info.recording_uuid == "deadbeef-dead-beef-dead-beefdeadbeef"

    def test_construction_with_mic_index(self) -> None:
        """mic_device_index can be set explicitly."""
        info = _skellycam_rust.RecordingInfo(
            "audio_test", "/tmp/recs", mic_device_index=2
        )
        assert info.mic_device_index == 2

    def test_from_dict(self) -> None:
        """from_dict() parses a dict matching the StartRecordingRequest body."""
        data = {
            "recording_name": "from_dict_test",
            "recording_directory": "/tmp/fdt",
            "mic_device_index": 3,
        }
        info = _skellycam_rust.RecordingInfo.from_dict(data)
        assert info.recording_name == "from_dict_test"
        assert info.recording_directory == "/tmp/fdt"
        assert info.mic_device_index == 3

    def test_path_properties(self) -> None:
        """Derived path properties follow the expected naming convention."""
        info = _skellycam_rust.RecordingInfo(
            "my_recording", "/data/recordings"
        )
        assert info.full_recording_path == "/data/recordings/my_recording"
        assert "synchronized_videos" in info.videos_folder
        assert "timestamps" in info.timestamps_folder
        assert "camera_timestamps" in info.camera_timestamps_folder
        assert info.recording_info_path.endswith("_info.json")
        assert info.audio_file_path.endswith(".audio.wav")

    def test_model_dump(self) -> None:
        """model_dump() returns a dict with the four stored fields."""
        info = _skellycam_rust.RecordingInfo(
            "dump_test", "/tmp/dumps", recording_uuid="fixed-uuid"
        )
        dumped = info.model_dump()
        assert dumped["recording_name"] == "dump_test"
        assert dumped["recording_directory"] == "/tmp/dumps"
        assert dumped["recording_uuid"] == "fixed-uuid"
        assert dumped["mic_device_index"] == -1

    def test_repr(self) -> None:
        """__repr__ includes name and directory."""
        info = _skellycam_rust.RecordingInfo("foo", "/bar")
        r = repr(info)
        assert "RecordingInfo" in r
        assert "foo" in r
        assert "/bar" in r


# ═══════════════════════════════════════════════════════════════════════════════
# StatsSummary
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestStatsSummary:
    """Tests for the ``StatsSummary`` PyO3 class."""

    def test_construction(self) -> None:
        """All five fields are stored correctly."""
        ss = _skellycam_rust.StatsSummary(
            median=30.0, mean=29.5, std=1.2, min=27.0, max=33.0
        )
        assert ss.median == pytest.approx(30.0)
        assert ss.mean == pytest.approx(29.5)
        assert ss.std == pytest.approx(1.2)
        assert ss.min == pytest.approx(27.0)
        assert ss.max == pytest.approx(33.0)

    def test_model_dump(self) -> None:
        """model_dump() returns a dict matching the OpenAPI StatsSummary schema."""
        ss = _skellycam_rust.StatsSummary(
            median=30.0, mean=29.5, std=1.2, min=27.0, max=33.0
        )
        dumped = ss.model_dump()
        assert dumped == {
            "median": 30.0,
            "mean": 29.5,
            "std": 1.2,
            "min": 27.0,
            "max": 33.0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# StopRecordingResponse
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestStopRecordingResponse:
    """Tests for the ``StopRecordingResponse`` PyO3 class."""

    def test_construction_with_nested_stats(self) -> None:
        """StopRecordingResponse holds three nested StatsSummary objects."""
        framerate_stats = _skellycam_rust.StatsSummary(30.0, 29.8, 0.5, 29.0, 31.0)
        frame_duration_stats = _skellycam_rust.StatsSummary(33.3, 33.5, 1.0, 32.0, 35.0)
        sync_stats = _skellycam_rust.StatsSummary(2.0, 2.1, 0.3, 1.5, 2.5)

        resp = _skellycam_rust.StopRecordingResponse(
            recording_name="test_rec",
            recording_path="/tmp/test_rec",
            number_of_cameras=2,
            number_of_frames=300,
            total_duration_sec=10.0,
            mean_framerate=30.0,
            mean_inter_camera_sync_ms=2.0,
            framerate_stats=framerate_stats,
            frame_duration_stats=frame_duration_stats,
            inter_camera_grab_range_ms_stats=sync_stats,
        )

        assert resp.recording_name == "test_rec"
        assert resp.recording_path == "/tmp/test_rec"
        assert resp.number_of_cameras == 2
        assert resp.number_of_frames == 300
        assert resp.total_duration_sec == pytest.approx(10.0)
        assert resp.mean_framerate == pytest.approx(30.0)
        assert resp.mean_inter_camera_sync_ms == pytest.approx(2.0)

    def test_model_dump_matches_openapi_schema(self) -> None:
        """model_dump() output has all keys required by the OpenAPI StopRecordingResponse."""
        fs = _skellycam_rust.StatsSummary(30.0, 29.8, 0.5, 29.0, 31.0)
        fds = _skellycam_rust.StatsSummary(33.3, 33.5, 1.0, 32.0, 35.0)
        ss = _skellycam_rust.StatsSummary(2.0, 2.1, 0.3, 1.5, 2.5)

        resp = _skellycam_rust.StopRecordingResponse(
            "rec", "/tmp/rec", 1, 100, 3.33, 30.0, 1.5, fs, fds, ss
        )
        dumped = resp.model_dump()

        required_keys = [
            "recording_name",
            "recording_path",
            "number_of_cameras",
            "number_of_frames",
            "total_duration_sec",
            "mean_framerate",
            "mean_inter_camera_sync_ms",
            "framerate_stats",
            "frame_duration_stats",
            "inter_camera_grab_range_ms_stats",
        ]
        for key in required_keys:
            assert key in dumped, f"Missing key: {key}"

        # Nested stats should be dicts
        assert isinstance(dumped["framerate_stats"], dict)
        assert dumped["framerate_stats"]["median"] == 30.0


# ═══════════════════════════════════════════════════════════════════════════════
# CameraStatusDict
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestCameraStatusDict:
    """Tests for the ``CameraStatusDict`` PyO3 class."""

    def test_default_construction(self) -> None:
        """Default status: connected, not closed, not recording, not paused, no error."""
        status = _skellycam_rust.CameraStatusDict()
        assert status.connected is True
        assert status.closed is False
        assert status.recording_in_progress is False
        assert status.is_paused is False
        assert status.error is False

    def test_custom_construction(self) -> None:
        """Custom status reflects the passed values."""
        status = _skellycam_rust.CameraStatusDict(
            connected=False,
            closed=True,
            recording_in_progress=True,
            is_paused=True,
            error=True,
        )
        assert status.connected is False
        assert status.closed is True
        assert status.recording_in_progress is True
        assert status.is_paused is True
        assert status.error is True

    def test_model_dump(self) -> None:
        """model_dump() returns all five boolean fields."""
        status = _skellycam_rust.CameraStatusDict(
            connected=True, closed=False, recording_in_progress=True,
            is_paused=False, error=False,
        )
        dumped = status.model_dump()
        assert dumped == {
            "connected": True,
            "closed": False,
            "recording_in_progress": True,
            "is_paused": False,
            "error": False,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FramerateData
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestFramerateData:
    """Tests for the ``FramerateData`` PyO3 class."""

    def test_construction(self) -> None:
        """All six fields are stored correctly."""
        fd = _skellycam_rust.FramerateData(
            mean_frame_duration_ms=33.3,
            mean_frames_per_second=30.0,
            frame_duration_stddev=1.5,
            frame_duration_median=33.0,
            calculation_window_size=100,
            framerate_source="Rust Backend",
        )
        assert fd.mean_frame_duration_ms == pytest.approx(33.3)
        assert fd.mean_frames_per_second == pytest.approx(30.0)
        assert fd.frame_duration_stddev == pytest.approx(1.5)
        assert fd.frame_duration_median == pytest.approx(33.0)
        assert fd.calculation_window_size == 100
        assert fd.framerate_source == "Rust Backend"

    def test_model_dump(self) -> None:
        """model_dump() returns a dict with all six fields."""
        fd = _skellycam_rust.FramerateData(33.3, 30.0, 1.5, 33.0, 100, "Rust Backend")
        dumped = fd.model_dump()
        assert dumped["mean_frame_duration_ms"] == 33.3
        assert dumped["mean_frames_per_second"] == 30.0
        assert dumped["frame_duration_stddev"] == 1.5
        assert dumped["frame_duration_median"] == 33.0
        assert dumped["calculation_window_size"] == 100
        assert dumped["framerate_source"] == "Rust Backend"


# ═══════════════════════════════════════════════════════════════════════════════
# detect_cameras
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestDetectCamerasFunction:
    """Tests for the ``detect_cameras()`` function."""

    def test_returns_list(self) -> None:
        """detect_cameras() returns a list (may be empty if no cameras)."""
        cameras = _skellycam_rust.detect_cameras()
        assert isinstance(cameras, list)

    def test_each_camera_has_expected_keys(self) -> None:
        """Each camera dict has keys matching CameraDeviceInfo schema."""
        cameras = _skellycam_rust.detect_cameras()
        for cam in cameras:
            assert "camera_index" in cam
            assert "display_name" in cam
            assert "unique_identifier" in cam
            assert "device_path" in cam
            assert "formats" in cam
            assert isinstance(cam["camera_index"], int)
            assert isinstance(cam["unique_identifier"], str)
            assert isinstance(cam["formats"], list)

    def test_unique_identifier_is_4_char_hex(self) -> None:
        """Each camera's unique_identifier is a 4-character hex string."""
        cameras = _skellycam_rust.detect_cameras()
        for cam in cameras:
            uid = cam["unique_identifier"]
            assert len(uid) == 4, f"Expected 4-char hex, got '{uid}'"
            # Should be valid lowercase hex
            int(uid, 16)  # raises ValueError if not hex

    def test_formats_have_expected_structure(self) -> None:
        """Each format entry has width, height, fps, fourcc, fourcc_str."""
        cameras = _skellycam_rust.detect_cameras()
        for cam in cameras:
            for fmt in cam.get("formats", []):
                assert "width" in fmt
                assert "height" in fmt
                assert "fps" in fmt
                assert "fourcc" in fmt
                assert "fourcc_str" in fmt
                assert isinstance(fmt["width"], int)
                assert isinstance(fmt["height"], int)
                assert isinstance(fmt["fps"], int)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level attributes
# ═══════════════════════════════════════════════════════════════════════════════

@requires_rust
class TestModuleAttributes:
    """Tests for ``_skellycam_rust`` module-level attributes."""

    def test_version_is_string(self) -> None:
        """__version__ is a non-empty string."""
        version = _skellycam_rust.__version__
        assert isinstance(version, str)
        assert len(version) > 0

    def test_doc_is_string(self) -> None:
        """__doc__ is a non-empty string."""
        doc = _skellycam_rust.__doc__
        assert isinstance(doc, str)
        assert len(doc) > 0
