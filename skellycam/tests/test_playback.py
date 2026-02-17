"""Tests for the playback router endpoints."""
from pathlib import Path
from unittest.mock import patch

import pytest

from skellycam.api.http.playback import playback_router as playback_module


@pytest.fixture(autouse=True)
def _reset_playback_state():
    """Reset module-level state between tests."""
    playback_module._loaded_videos = {}
    playback_module._loaded_recording_path = None
    yield
    playback_module._loaded_videos = {}
    playback_module._loaded_recording_path = None


@pytest.fixture()
def fake_recording(tmp_path: Path) -> Path:
    """Create a fake recording directory with dummy video files."""
    videos_dir = tmp_path / "synchronized_videos"
    videos_dir.mkdir(parents=True)

    # Create minimal but valid-ish files (actual playback isn't tested, just serving)
    for cam_id in ["camera0", "camera1"]:
        video_file = videos_dir / f"recording.{cam_id}.mp4"
        video_file.write_bytes(b"\x00" * 1024)  # Dummy bytes

    # Create a timestamp CSV
    ts_dir = videos_dir / "timestamps" / "camera_timestamps"
    ts_dir.mkdir(parents=True)
    ts_file = ts_dir / "recording.camera0.timestamps.csv"
    ts_file.write_text("frame_number,timestamp_ns\n0,1000000\n1,1033333\n")

    return tmp_path


class TestListRecordings:
    def test_list_recordings_empty(self, client):
        """GET /skellycam/playback/recordings returns empty list when no recordings exist."""
        with patch(
            "skellycam.api.http.playback.playback_router.get_default_skellycam_recordings_path",
            return_value="/nonexistent/path",
        ):
            response = client.get("/skellycam/playback/recordings")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_recordings_with_data(self, client, fake_recording):
        """GET /skellycam/playback/recordings lists recording directories."""
        recordings_dir = fake_recording.parent
        with patch(
            "skellycam.api.http.playback.playback_router.get_default_skellycam_recordings_path",
            return_value=str(recordings_dir),
        ):
            response = client.get("/skellycam/playback/recordings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == fake_recording.name
        assert data[0]["video_count"] == 2


class TestLoadRecording:
    def test_load_valid_recording(self, client, fake_recording):
        """POST /skellycam/playback/load returns video metadata."""
        response = client.post(
            "/skellycam/playback/load",
            json={"recording_path": str(fake_recording)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["recording_path"] == str(fake_recording)
        assert len(data["videos"]) == 2

        # Check video info structure
        video_ids = {v["video_id"] for v in data["videos"]}
        assert "recording.camera0" in video_ids
        assert "recording.camera1" in video_ids

        for v in data["videos"]:
            assert v["stream_url"].startswith("/skellycam/playback/video/")
            assert v["size_bytes"] == 1024

    def test_load_nonexistent_path(self, client):
        """POST /skellycam/playback/load returns 404 for missing directory."""
        response = client.post(
            "/skellycam/playback/load",
            json={"recording_path": "/nonexistent/path"},
        )
        assert response.status_code == 404

    def test_load_empty_directory(self, client, tmp_path):
        """POST /skellycam/playback/load returns 404 for directory without videos."""
        response = client.post(
            "/skellycam/playback/load",
            json={"recording_path": str(tmp_path)},
        )
        assert response.status_code == 404


class TestStreamVideo:
    def test_stream_loaded_video(self, client, fake_recording):
        """GET /skellycam/playback/video/{id} serves the file after loading."""
        # First load
        client.post(
            "/skellycam/playback/load",
            json={"recording_path": str(fake_recording)},
        )
        # Then stream
        response = client.get("/skellycam/playback/video/recording.camera0")
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert len(response.content) == 1024

    def test_stream_unloaded_video(self, client):
        """GET /skellycam/playback/video/{id} returns 404 when nothing loaded."""
        response = client.get("/skellycam/playback/video/nonexistent")
        assert response.status_code == 404


class TestTimestamps:
    def test_get_timestamps(self, client, fake_recording):
        """GET /skellycam/playback/timestamps/{id} returns CSV info."""
        client.post(
            "/skellycam/playback/load",
            json={"recording_path": str(fake_recording)},
        )
        response = client.get("/skellycam/playback/timestamps/camera0")
        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "camera0"
        assert data["row_count"] == 2
        assert "frame_number" in data["headers"]

    def test_get_timestamps_not_found(self, client, fake_recording):
        """GET /skellycam/playback/timestamps/{id} returns 404 for unknown video."""
        client.post(
            "/skellycam/playback/load",
            json={"recording_path": str(fake_recording)},
        )
        response = client.get("/skellycam/playback/timestamps/nonexistent")
        assert response.status_code == 404
