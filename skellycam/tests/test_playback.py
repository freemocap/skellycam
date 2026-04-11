"""Tests for the playback router endpoints."""
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def fake_recording(tmp_path: Path) -> Path:
    """Create a fake recording directory with dummy video files.

    The recording lives inside a 'recordings_root' parent so we can
    use tmp_path / "recordings_root" as the default recordings directory
    and the folder name as the recording_id.
    """
    recordings_root = tmp_path / "recordings_root"
    rec_dir = recordings_root / "my_recording"
    videos_dir = rec_dir / "synchronized_videos"
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

    return rec_dir


def _recordings_root(fake_recording: Path) -> str:
    """Return the parent directory that contains the recording folder."""
    return str(fake_recording.parent)


def _recording_id(fake_recording: Path) -> str:
    """Return the recording folder name (used as recording_id in URLs)."""
    return fake_recording.name


class TestListRecordings:
    def test_list_recordings_empty(self, client):
        """GET /recordings/recordings returns empty list when no recordings exist."""
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value="/nonexistent/path",
        ):
            response = client.get("/recordings/recordings")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_recordings_with_data(self, client, fake_recording):
        """GET /recordings/recordings lists recording directories."""
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get("/recordings/recordings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["video_count"] == 2
        assert data[0]["name"] == _recording_id(fake_recording)

    def test_list_recordings_with_parent_directory_param(self, client, fake_recording):
        """GET /recordings/recordings?recording_parent_directory=... overrides default."""
        response = client.get(
            "/recordings/recordings",
            params={"recording_parent_directory": _recordings_root(fake_recording)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == _recording_id(fake_recording)


class TestListVideos:
    def test_list_videos(self, client, fake_recording):
        """GET /recordings/{recording_id}/videos returns video metadata."""
        rec_id = _recording_id(fake_recording)
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get(f"/recordings/{rec_id}/videos")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        video_ids = {v["video_id"] for v in data}
        assert "recording.camera0" in video_ids
        assert "recording.camera1" in video_ids

        for v in data:
            assert v["stream_url"].startswith(f"/recordings/{rec_id}/videos/")
            assert v["size_bytes"] == 1024

    def test_list_videos_with_parent_dir(self, client, fake_recording):
        """GET with recording_parent_directory query param works."""
        rec_id = _recording_id(fake_recording)
        response = client.get(
            f"/recordings/{rec_id}/videos",
            params={"recording_parent_directory": _recordings_root(fake_recording)},
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_videos_nonexistent(self, client):
        """GET returns 404 for nonexistent recording."""
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value="/nonexistent/path",
        ):
            response = client.get("/recordings/does_not_exist/videos")
        assert response.status_code == 404


class TestStreamVideo:
    def test_stream_video(self, client, fake_recording):
        """GET /recordings/{recording_id}/videos/{video_id} serves the file."""
        rec_id = _recording_id(fake_recording)
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get(f"/recordings/{rec_id}/videos/recording.camera0")
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert len(response.content) == 1024

    def test_stream_nonexistent_video(self, client, fake_recording):
        """GET returns 404 for unknown video_id."""
        rec_id = _recording_id(fake_recording)
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get(f"/recordings/{rec_id}/videos/nonexistent")
        assert response.status_code == 404


class TestTimestamps:
    def test_get_all_timestamps(self, client, fake_recording):
        """GET /recordings/{recording_id}/timestamps returns timestamps with warnings."""
        rec_id = _recording_id(fake_recording)
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get(f"/recordings/{rec_id}/timestamps")
        assert response.status_code == 200
        data = response.json()
        assert "timestamps" in data
        assert "warnings" in data

    def test_get_video_timestamps(self, client, fake_recording):
        """GET /recordings/{recording_id}/videos/{video_id}/timestamps returns CSV info."""
        rec_id = _recording_id(fake_recording)
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get(f"/recordings/{rec_id}/videos/camera0/timestamps")
        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "camera0"
        assert data["row_count"] == 2
        assert "frame_number" in data["headers"]

    def test_get_video_timestamps_not_found_returns_warning(self, client, fake_recording):
        """GET returns warning (not 404) for unknown video timestamps."""
        rec_id = _recording_id(fake_recording)
        with patch(
            "skellycam.api.http.recordings.recordings_router.get_default_skellycam_recordings_path",
            return_value=_recordings_root(fake_recording),
        ):
            response = client.get(f"/recordings/{rec_id}/videos/nonexistent/timestamps")
        assert response.status_code == 200
        data = response.json()
        assert "warning" in data
        assert data["row_count"] == 0
