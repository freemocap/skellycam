import json
from pathlib import Path

from skellycam.core.recorders.videos.video_associations import VideoAssociations
from skellycam.core.timestamps.recording_timing_reader import recorded_camera_timing_path, resolve_camera_timing


def test_recording_name_does_not_control_declared_file_relationships(tmp_path: Path) -> None:
    metadata = {"videos": {"source": "arbitrary.avi"}, "camera_timing": {"source": "timing.csv"}}
    (tmp_path / "original_name_info.json").write_text(json.dumps(metadata), encoding="utf-8")
    timing_path = tmp_path / "timing.csv"
    timing_path.write_text("recording_frame_number,timestamp.from_recording_start.sec\n0,0.2\n1,0.3\n", encoding="utf-8")
    associations = VideoAssociations.from_recording_folder(recording_folder=tmp_path)
    assert associations is not None
    assert associations.root == metadata["videos"]
    path = recorded_camera_timing_path(recording_folder=tmp_path, camera_id="source")
    assert path == timing_path
    assert resolve_camera_timing(path=path, frame_count=2, fps=30.0, offset_s=0.0).timestamps_s == (0.2, 0.3)


def test_unrelated_timing_metadata_does_not_invalidate_video_associations(tmp_path: Path) -> None:
    (tmp_path / "recording_info.json").write_text(json.dumps({"videos": {"source": "video.avi"}, "camera_timing": 42}), encoding="utf-8")
    associations = VideoAssociations.from_recording_folder(recording_folder=tmp_path)
    assert associations is not None
    assert associations.root == {"source": "video.avi"}
