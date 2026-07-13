"""Regression tests for skellycam.opencv.video_recorder.video_recorder.VideoRecorder
after its rewrite onto StreamingVideoWriter.
"""
import numpy as np
import pytest

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.opencv.video_recorder.streaming_video_writer import (
    Cv2FrameEncoder,
    WriterFailedError,
    WriterSaturatedError,
)

from skellycam.tests.test_streaming_video_writer import FakeEncoder


def make_frame_payload(camera_id: str = "0", timestamp_ns: int = 0) -> FramePayload:
    return FramePayload(
        success=True,
        image=np.zeros((4, 4, 3), dtype=np.uint8),
        timestamp_ns=timestamp_ns,
        camera_id=camera_id,
    )


class TestUnboundedListRemoved:
    def test_no_frame_payload_list_attribute_exists(self):
        """Regression guard for the actual root cause: VideoRecorder must
        never again accumulate frames in an unbounded list."""
        recorder = VideoRecorder()
        assert not hasattr(recorder, "_frame_payload_list")
        assert not hasattr(recorder, "frame_payload_list")

    def test_no_cv2_video_writer_instance_state(self):
        recorder = VideoRecorder()
        assert not hasattr(recorder, "_cv2_video_writer")

    def test_number_of_frames_is_zero_before_streaming(self):
        recorder = VideoRecorder()
        assert recorder.number_of_frames == 0


class TestStreamingLifecycleViaVideoRecorder:
    def test_start_submit_stop_cycle(self, tmp_path, monkeypatch):
        recorder = VideoRecorder()
        # substitute the internal encoder with a fake one via the module-level
        # default -- simplest is to monkeypatch Cv2FrameEncoder used inside
        # StreamingVideoWriter's default construction path.
        import skellycam.opencv.video_recorder.streaming_video_writer as sv_module
        monkeypatch.setattr(sv_module, "Cv2FrameEncoder", lambda *a, **kw: FakeEncoder())

        recorder.start_streaming(video_file_save_path=tmp_path / "Camera_000_synchronized.mp4", expected_fps=30.0)
        for i in range(5):
            recorder.append_frame_payload_to_list(make_frame_payload(timestamp_ns=i * 1_000), frame_index=i)

        assert recorder.number_of_frames == 5

        result = recorder.stop_streaming(timeout_seconds=5)
        assert result.success
        assert result.frames_written == 5

    def test_append_requires_frame_index(self, tmp_path, monkeypatch):
        import skellycam.opencv.video_recorder.streaming_video_writer as sv_module
        monkeypatch.setattr(sv_module, "Cv2FrameEncoder", lambda *a, **kw: FakeEncoder())

        recorder = VideoRecorder()
        recorder.start_streaming(video_file_save_path=tmp_path / "cam.mp4", expected_fps=30.0)
        with pytest.raises(TypeError):
            recorder.append_frame_payload_to_list(make_frame_payload())  # missing frame_index -- signature is intentionally required, see checkpoint report

    def test_append_before_start_raises(self):
        recorder = VideoRecorder()
        with pytest.raises(RuntimeError):
            recorder.append_frame_payload_to_list(make_frame_payload(), frame_index=0)

    def test_abort_streaming_marks_unhealthy_and_preserves_partial(self, tmp_path, monkeypatch):
        import skellycam.opencv.video_recorder.streaming_video_writer as sv_module
        monkeypatch.setattr(sv_module, "Cv2FrameEncoder", lambda *a, **kw: FakeEncoder())

        output_path = tmp_path / "cam.mp4"
        recorder = VideoRecorder()
        recorder.start_streaming(video_file_save_path=output_path, expected_fps=30.0)
        recorder.append_frame_payload_to_list(make_frame_payload(), frame_index=0)

        result = recorder.abort_streaming(reason="test abort")
        assert not result.success
        assert not output_path.exists()


class TestLegacyCalibrationPathUnchanged:
    """save_image_list_to_disk operates on an already-complete, caller-owned
    list -- it was never implicated in the unbounded-memory bug and must
    keep working exactly as before."""

    def test_save_image_list_to_disk_still_works(self, tmp_path):
        recorder = VideoRecorder()
        images = [np.zeros((4, 4, 3), dtype=np.uint8) for _ in range(3)]
        output_path = tmp_path / "calibration.mp4"
        recorder.save_image_list_to_disk(
            image_list=images, path_to_save_video_file=output_path, frames_per_second=30.0,
        )
        assert output_path.exists()

    def test_save_image_list_to_disk_handles_empty_list(self, tmp_path):
        recorder = VideoRecorder()
        recorder.save_image_list_to_disk(
            image_list=[], path_to_save_video_file=tmp_path / "empty.mp4", frames_per_second=30.0,
        )  # should log and return, not raise
