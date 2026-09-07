import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from skellycam.core.recorders.videos.video_associations import VideoAssociations
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.camera.config.camera_config import CameraConfig


def test_arbitrary_names_preserve_declared_source_order(tmp_path: Path) -> None:
    for name in ("holiday 2026.mp4", "camera nineteen.mov"):
        (tmp_path / name).touch()
    associations = VideoAssociations({"right": "holiday 2026.mp4", "left": "camera nineteen.mov"})
    assert associations.resolve_paths(video_folder=tmp_path) == {
        "right": tmp_path / "holiday 2026.mp4",
        "left": tmp_path / "camera nineteen.mov",
    }


def test_duplicate_file_association_fails(tmp_path: Path) -> None:
    (tmp_path / "clip.mp4").touch()
    with pytest.raises(ValueError, match="same video"):
        VideoAssociations({"one": "clip.mp4", "two": "./clip.mp4"}).resolve_paths(video_folder=tmp_path)


@pytest.mark.parametrize("filename", ["../clip.mp4", "C:/clip.mp4", "/clip.mp4", "", "..\\clip.mp4"])
def test_paths_cannot_escape_recording(filename: str) -> None:
    with pytest.raises(ValidationError):
        VideoAssociations({"camera": filename})


def test_missing_declared_video_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        VideoAssociations({"camera": "missing.mp4"}).resolve_paths(video_folder=tmp_path)


def test_invalid_source_fails() -> None:
    with pytest.raises(ValidationError):
        VideoAssociations({" ": "clip.mp4"})


def test_capture_publishes_actual_container_and_source(tmp_path: Path) -> None:
    recording = RecordingInfo(recording_directory=str(tmp_path), recording_name="capture")
    config = CameraConfig(camera_id="source", camera_index=2)
    video = Path(recording.video_file_path_from_camera_config(config=config, extension="avi"))
    video.touch()
    recording.save_to_file(camera_configs={config.camera_id: config})
    metadata = json.loads(Path(recording.recording_info_path).read_text())
    assert metadata["videos"] == {config.camera_id: video.name}


def test_capture_rejects_multiple_container_candidates(tmp_path: Path) -> None:
    recording = RecordingInfo(recording_directory=str(tmp_path), recording_name="capture")
    config = CameraConfig(camera_id="source", camera_index=2)
    video = Path(recording.video_file_path_from_camera_config(config=config, extension="mp4"))
    video.touch()
    video.with_suffix(".avi").touch()
    with pytest.raises(ValueError, match="Multiple videos"):
        recording.save_to_file(camera_configs={config.camera_id: config})
    assert not Path(recording.recording_info_path).exists()
