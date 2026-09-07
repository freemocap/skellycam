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


def test_read_declared_identity_does_not_parse_filename(tmp_path: Path) -> None:
    metadata = tmp_path / f"{tmp_path.name}_info.json"
    metadata.write_text(json.dumps({"videos": {"actual-source": "camera_99.mp4"}}), encoding="utf-8")
    associations = VideoAssociations.from_recording_folder(recording_folder=tmp_path)
    assert associations is not None
    assert associations.source_for_path(video_folder=tmp_path, video_path=tmp_path / "camera_99.mp4") == "actual-source"
    assert associations.source_for_path(video_folder=tmp_path, video_path=tmp_path / "camera_99_annotated.mp4") is None


def test_other_missing_file_does_not_block_source_lookup(tmp_path: Path) -> None:
    associations = VideoAssociations({"first": "present.mp4", "second": "missing.mp4"})
    (tmp_path / "present.mp4").touch()
    assert associations.source_for_path(video_folder=tmp_path, video_path=tmp_path / "present.mp4") == "first"


def test_conflicting_recording_declarations_fail(tmp_path: Path) -> None:
    for suffix, filename in (("info", "first.mp4"), ("recording_info", "second.mp4")):
        (tmp_path / f"{tmp_path.name}_{suffix}.json").write_text(
            json.dumps({"videos": {"source": filename}}), encoding="utf-8",
        )
    with pytest.raises(ValueError, match="Conflicting"):
        VideoAssociations.from_recording_folder(recording_folder=tmp_path)


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
