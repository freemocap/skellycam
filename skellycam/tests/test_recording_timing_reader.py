"""Recorded timing takes precedence; absent sidecars permit nominal-FPS timing."""

from pathlib import Path

import pytest

from skellycam.core.timestamps.recording_timing_reader import resolve_camera_timing


def test_inferred_timing_retains_supplied_offset(tmp_path: Path) -> None:
    result = resolve_camera_timing(
        path=None, frame_count=3, fps=120.0, offset_s=2.0
    )
    assert result.method == "inferred_from_fps"
    assert result.timestamps_s == (2.0, 2.0 + 1 / 120, 2.0 + 2 / 120)


def test_recorded_timing_is_not_rebased(tmp_path: Path) -> None:
    path = tmp_path / "camera.csv"
    path.write_text(
        "# recording_frame_number,timestamp.from_recording_start.sec\n0,0.012\n1,0.049\n",
        encoding="utf-8",
    )
    result = resolve_camera_timing(path=path, frame_count=2, fps=30.0, offset_s=2.0)
    assert result.method == "recorded"
    assert result.timestamps_s == (0.012, 0.049)


@pytest.mark.parametrize("fps", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_fps_cannot_generate_timing(tmp_path: Path, fps: float) -> None:
    with pytest.raises(ValueError, match="positive FPS"):
        resolve_camera_timing(
            path=None, frame_count=2, fps=fps, offset_s=0.0
        )


def test_partial_sidecar_does_not_fall_back_to_fps(tmp_path: Path) -> None:
    path = tmp_path / "camera.csv"
    path.write_text(
        "recording_frame_number,timestamp.from_recording_start.sec\n0,0.01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cover the video frame grid"):
        resolve_camera_timing(path=path, frame_count=2, fps=30.0, offset_s=0.0)
