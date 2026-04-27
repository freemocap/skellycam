"""Tests for frontend payload serialization, recording info, and descriptive statistics."""
import uuid
from pathlib import Path

import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera.config.image_rotation_types import RotationTypes, rotation_int_to_name
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.frontend_payload_bytearray import (
    FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE,
    FRONTEND_FRAME_HEADER_DTYPE,
    MessageType,
    create_frontend_payload,
)
from skellycam.core.types.frame_dtype_factories import create_frame_dtype, create_multiframe_dtype
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE, FRAME_CAMERA_INFO_DTYPE
from skellycam.utilities.descriptive_statistics import DescriptiveStatistics


# ---------------------------------------------------------------------------
# Frontend Payload Protocol
# ---------------------------------------------------------------------------

class TestFrontendPayloadProtocol:
    @staticmethod
    def _make_fake_frames(
        camera_ids: list[str],
        frame_number: int = 42,
    ) -> dict[str, np.recarray]:
        """Create minimal fake frame recarrays for payload testing."""
        frames: dict[str, np.recarray] = {}
        for i, cam_id in enumerate(camera_ids):
            config = CameraConfig(
                camera_id=cam_id,
                camera_index=i,
                resolution=ImageResolution(height=48, width=64),
            )
            frame_dtype = create_frame_dtype(config)
            frame = np.recarray(1, dtype=frame_dtype)
            frame.frame_metadata.camera_info[0] = config.to_frame_camera_info()
            frame.frame_metadata.frame_number[0] = frame_number
            frame.frame_metadata.timestamps.pre_frame_grab_ns[0] = 1_000_000_000
            frame.frame_metadata.timestamps.post_frame_grab_ns[0] = 1_001_000_000
            frame.image[0] = np.random.randint(0, 255, (48, 64, 3), dtype=np.uint8)
            frames[cam_id] = frame
        return frames

    def test_single_camera_payload_structure(self) -> None:
        frames = self._make_fake_frames(["cam0"], frame_number=10)
        frame_number, timestamp, payload_bytes = create_frontend_payload(
            latest_frames=frames,
        )

        assert frame_number == 10
        assert isinstance(payload_bytes, (bytes, bytearray))
        assert len(payload_bytes) > 0

        # Parse the header
        header_size = FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
        header = np.frombuffer(payload_bytes[:header_size], dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
        assert int(header["message_type"][0]) == MessageType.PAYLOAD_HEADER
        assert int(header["frame_number"][0]) == 10
        assert int(header["number_of_cameras"][0]) == 1

        # Parse the footer (last N bytes)
        footer_size = FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
        footer = np.frombuffer(
            payload_bytes[len(payload_bytes) - footer_size:],
            dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE,
        )
        assert int(footer["message_type"][0]) == MessageType.PAYLOAD_FOOTER
        assert int(footer["frame_number"][0]) == 10

    def test_multi_camera_payload(self) -> None:
        frames = self._make_fake_frames(["cam0", "cam1", "cam2"], frame_number=99)
        frame_number, timestamp, payload_bytes = create_frontend_payload(
            latest_frames=frames,
        )

        assert frame_number == 99
        header_size = FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
        header = np.frombuffer(payload_bytes[:header_size], dtype=FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
        assert int(header["number_of_cameras"][0]) == 3

    def test_payload_contains_jpeg_data(self) -> None:
        frames = self._make_fake_frames(["cam0"], frame_number=1)
        _, _, payload_bytes = create_frontend_payload(latest_frames=frames)

        # After header + frame_header, there should be JPEG data
        # JPEG files start with 0xFF 0xD8
        header_size = FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE.itemsize
        frame_header_size = FRONTEND_FRAME_HEADER_DTYPE.itemsize
        jpeg_start = header_size + frame_header_size
        assert payload_bytes[jpeg_start] == 0xFF
        assert payload_bytes[jpeg_start + 1] == 0xD8


# ---------------------------------------------------------------------------
# Numpy Dtype Construction
# ---------------------------------------------------------------------------

class TestNumpyDtypes:
    def test_create_frame_dtype(self) -> None:
        config = CameraConfig(
            resolution=ImageResolution(height=48, width=64),
            color_channels=3,
        )
        dtype = create_frame_dtype(config)
        assert "frame_metadata" in dtype.names
        assert "image" in dtype.names

    def test_create_multiframe_dtype(self) -> None:
        configs = {
            "cam0": CameraConfig(camera_id="cam0", camera_index=0, resolution=ImageResolution(height=48, width=64)),
            "cam1": CameraConfig(camera_id="cam1", camera_index=1, resolution=ImageResolution(height=48, width=64)),
        }
        dtype = create_multiframe_dtype(configs)
        assert "cam0" in dtype.names
        assert "cam1" in dtype.names

    def test_frame_metadata_dtype_has_expected_fields(self) -> None:
        assert "camera_info" in FRAME_METADATA_DTYPE.names
        assert "frame_number" in FRAME_METADATA_DTYPE.names
        assert "timebase_mapping" in FRAME_METADATA_DTYPE.names
        assert "timestamps" in FRAME_METADATA_DTYPE.names


# ---------------------------------------------------------------------------
# RecordingInfo
# ---------------------------------------------------------------------------

class TestRecordingInfo:
    def test_create_temp(self) -> None:
        info = RecordingInfo.create_temp()
        assert len(info.recording_name) > 0
        assert len(info.recording_uuid) > 0
        assert info.mic_device_index == -1

    def test_paths_are_consistent(self) -> None:
        info = RecordingInfo(
            recording_name="test_recording",
            recording_directory="/tmp/skellycam_test",
        )
        assert "test_recording" in info.full_recording_path
        assert "synchronized_videos" in info.videos_folder
        assert "timestamps" in info.timestamps_folder
        assert info.recording_name in info.timestamp_file_path
        assert info.audio_file_path.endswith(".wav")

    def test_video_file_path_from_config(self) -> None:
        info = RecordingInfo(
            recording_name="rec",
            recording_directory="/tmp/test",
        )
        config = CameraConfig(camera_id="cam0", camera_index=0)
        path = info.video_file_path_from_camera_config(config)
        assert "cam0" in path
        assert "idx0" in path

    def test_camera_timestamps_path(self) -> None:
        info = RecordingInfo(
            recording_name="rec",
            recording_directory="/tmp/test",
        )
        path = info.camera_timestamps_file_path_from_camera_id("cam0")
        assert "cam0" in path
        assert path.endswith(".csv")

    def test_equality(self) -> None:
        shared_ts = RecordingInfo.create_temp().recording_start_timestamp
        a = RecordingInfo(recording_name="a", recording_directory="/tmp/a", recording_uuid="uuid1", recording_start_timestamp=shared_ts)
        b = RecordingInfo(recording_name="a", recording_directory="/tmp/a", recording_uuid="uuid1", recording_start_timestamp=shared_ts)
        c = RecordingInfo(recording_name="c", recording_directory="/tmp/c", recording_uuid="uuid2", recording_start_timestamp=shared_ts)
        assert a == b
        assert a != c

    def test_str(self) -> None:
        info = RecordingInfo.create_temp()
        s = str(info)
        assert "RecordingInfo" in s
        assert info.recording_name in s


# ---------------------------------------------------------------------------
# RotationTypes utilities
# ---------------------------------------------------------------------------

class TestRotationTypes:
    def test_rotation_int_to_name_known(self) -> None:
        assert rotation_int_to_name(-1) == "NO_ROTATION"
        assert rotation_int_to_name(1) == "ROTATE_180"

    def test_rotation_int_to_name_unknown(self) -> None:
        assert rotation_int_to_name(9999) == "UNKNOWN_ROTATION"


# ---------------------------------------------------------------------------
# DescriptiveStatistics
# ---------------------------------------------------------------------------

class TestDescriptiveStatistics:
    def test_basic_statistics(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = DescriptiveStatistics.from_samples(samples=data, name="test", units="ms")
        assert stats.mean == pytest.approx(3.0)
        assert stats.median == pytest.approx(3.0)
        assert stats.min == pytest.approx(1.0)
        assert stats.max == pytest.approx(5.0)
        assert stats.range == pytest.approx(4.0)
        assert stats.number_of_samples == 5

    def test_single_sample(self) -> None:
        stats = DescriptiveStatistics.from_samples(samples=[42.0], name="single")
        assert stats.mean == pytest.approx(42.0)
        assert stats.standard_deviation == pytest.approx(0.0)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            DescriptiveStatistics.from_samples(samples=[], name="empty")

    def test_numpy_array_input(self) -> None:
        data = np.array([10.0, 20.0, 30.0])
        stats = DescriptiveStatistics.from_samples(samples=data, name="numpy")
        assert stats.mean == pytest.approx(20.0)

    def test_str_representation(self) -> None:
        stats = DescriptiveStatistics.from_samples(
            samples=[1.0, 2.0, 3.0, 4.0, 5.0],
            name="test",
            units="Hz",
        )
        s = str(stats)
        assert "test" in s
        assert "Hz" in s

    def test_model_dump(self) -> None:
        stats = DescriptiveStatistics.from_samples(
            samples=[1.0, 2.0, 3.0],
            name="dump_test",
            units="s",
        )
        d = stats.model_dump()
        assert isinstance(d, dict)
        assert d["name"] == "dump_test"
        assert d["units"] == "s"
        assert "max" in d
        assert "min" in d
