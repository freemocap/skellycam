from pathlib import Path

import pytest

from skellycam.core.recorders.videos.video_copy_plan import VideoCopyPlan


def test_copy_preserves_explicit_names_and_content(tmp_path: Path) -> None:
    source = tmp_path / "arbitrary name.mp4"
    source.write_bytes(b"video payload")
    output = tmp_path / "output"
    plan = VideoCopyPlan.create(source_files=(source,), destination_folder=output,
                                destination_names=("selected.mov",))
    assert not output.exists()
    plan.copy_files()
    assert (output / "selected.mov").read_bytes() == source.read_bytes()


def test_collision_fails_before_any_copy(tmp_path: Path) -> None:
    sources = (tmp_path / "first.mp4", tmp_path / "second.mp4")
    for path in sources:
        path.touch()
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="colliding"):
        VideoCopyPlan.create(source_files=sources, destination_folder=output,
                             destination_names=("clip.mp4", "CLIP.mp4"))
    assert not output.exists()


def test_file_created_after_validation_is_not_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    destination = tmp_path / "destination.mp4"
    plan = VideoCopyPlan.create(source_files=(source,), destination_folder=tmp_path,
                                destination_names=(destination.name,))
    destination.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        plan.copy_files()
    assert destination.read_bytes() == b"keep"


def test_missing_later_source_prevents_copy(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.touch()
    output = tmp_path / "output"
    with pytest.raises(FileNotFoundError):
        VideoCopyPlan.create(source_files=(source, tmp_path / "missing.mp4"),
                             destination_folder=output, destination_names=("first.mp4", "second.mp4"))
    assert not output.exists()


def test_duplicate_source_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.touch()
    with pytest.raises(ValueError, match="more than once"):
        VideoCopyPlan.create(source_files=(source, source), destination_folder=tmp_path / "output",
                             destination_names=("first.mp4", "second.mp4"))
