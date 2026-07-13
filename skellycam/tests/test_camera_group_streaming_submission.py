"""Regression tests for CamGroupThreadWorker's synchronized-frame-bundle
submission path (_try_record_synchronized_frame_bundle / _abort_recording).

These exercise the real production methods directly, with a fake camera
group double and monkeypatched encoder -- no real camera, no QThread.start(),
no Qt event loop required. See the checkpoint report for why the full
QThread-based VideoSaveThreadWorker path is not exercised here.
"""
import numpy as np
import pytest

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.gui.qt.workers.camera_group_thread_worker import CamGroupThreadWorker
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

from skellycam.tests.test_streaming_video_writer import FakeEncoder


class FakeCameraConfig:
    def __init__(self, framerate=30):
        self.framerate = framerate
        self.use_this_camera = True


class FakeCameraGroup:
    """Minimal double: only what _initialize_video_recorder_dictionary()
    and start_recording() actually touch."""

    def __init__(self, camera_ids):
        self.camera_config_dictionary = {cam_id: FakeCameraConfig() for cam_id in camera_ids}


def make_frame_payload(camera_id: str, timestamp_ns: int) -> FramePayload:
    return FramePayload(
        success=True,
        image=np.zeros((4, 4, 3), dtype=np.uint8),
        timestamp_ns=timestamp_ns,
        camera_id=camera_id,
    )


@pytest.fixture
def worker(tmp_path, monkeypatch):
    import skellycam.opencv.video_recorder.streaming_video_writer as sv_module
    monkeypatch.setattr(sv_module, "Cv2FrameEncoder", lambda *a, **kw: FakeEncoder())

    w = CamGroupThreadWorker(
        camera_ids=None,  # avoids constructing a real CameraGroup / opening real cameras
        get_new_synchronized_videos_folder_callable=lambda: tmp_path,
    )
    return w


def start_recorder(worker, tmp_path, camera_id: str) -> VideoRecorder:
    recorder = VideoRecorder()
    recorder.start_streaming(
        video_file_save_path=tmp_path / f"Camera_{camera_id}_synchronized.mp4",
        expected_fps=30.0,
    )
    return recorder


class TestSingleGlobalFrameIndex:
    def test_one_bundle_gets_one_global_index_single_camera(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0"])
        worker._video_recorder_dictionary = {"0": start_recorder(worker, tmp_path, "0")}

        worker._try_record_synchronized_frame_bundle({"0": make_frame_payload("0", 0)})
        assert worker._next_frame_index == 1
        assert worker._video_recorder_dictionary["0"].number_of_frames == 1

    def test_multiple_bundles_increment_monotonically_no_duplicates(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0"])
        worker._video_recorder_dictionary = {"0": start_recorder(worker, tmp_path, "0")}

        for i in range(10):
            worker._try_record_synchronized_frame_bundle({"0": make_frame_payload("0", i * 33_000_000)})

        assert worker._next_frame_index == 10
        assert worker._video_recorder_dictionary["0"].number_of_frames == 10

    def test_two_aligned_cameras_get_the_same_frame_index(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0", "1"])
        worker._video_recorder_dictionary = {
            "0": start_recorder(worker, tmp_path, "0"),
            "1": start_recorder(worker, tmp_path, "1"),
        }

        worker._try_record_synchronized_frame_bundle({
            "0": make_frame_payload("0", 1_000_000),
            "1": make_frame_payload("1", 1_002_000),  # 2us apart -- well within threshold
        })

        assert worker._video_recorder_dictionary["0"].number_of_frames == 1
        assert worker._video_recorder_dictionary["1"].number_of_frames == 1
        assert worker._next_frame_index == 1


class TestMissingCameraPreventsCommit:
    def test_missing_camera_does_not_commit_bundle(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0", "1"])
        worker._video_recorder_dictionary = {
            "0": start_recorder(worker, tmp_path, "0"),
            "1": start_recorder(worker, tmp_path, "1"),
        }

        # camera "1" has no frame this iteration -- must not partially commit
        worker._try_record_synchronized_frame_bundle({"0": make_frame_payload("0", 0)})

        assert worker._next_frame_index == 0
        assert worker._video_recorder_dictionary["0"].number_of_frames == 0
        assert worker._video_recorder_dictionary["1"].number_of_frames == 0

    def test_none_frame_payload_treated_as_missing(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0", "1"])
        worker._video_recorder_dictionary = {
            "0": start_recorder(worker, tmp_path, "0"),
            "1": start_recorder(worker, tmp_path, "1"),
        }

        worker._try_record_synchronized_frame_bundle({"0": make_frame_payload("0", 0), "1": None})

        assert worker._next_frame_index == 0


class TestStaleFrameGuard:
    def test_frames_too_far_apart_in_time_are_not_paired(self, worker, tmp_path):
        """The gap this checkpoint asked about: without this guard, a
        backlogged frame from a slow camera could be silently paired with a
        fresh frame from a fast one under the same frame_index."""
        worker._camera_group = FakeCameraGroup(["0", "1"])
        worker._video_recorder_dictionary = {
            "0": start_recorder(worker, tmp_path, "0"),
            "1": start_recorder(worker, tmp_path, "1"),
        }
        worker._max_frame_bundle_timestamp_delta_ns = 50_000_000  # 50ms

        worker._try_record_synchronized_frame_bundle({
            "0": make_frame_payload("0", 0),
            "1": make_frame_payload("1", 200_000_000),  # 200ms apart -- well outside threshold
        })

        assert worker._next_frame_index == 0
        assert worker._video_recorder_dictionary["0"].number_of_frames == 0
        assert worker._video_recorder_dictionary["1"].number_of_frames == 0

    def test_frames_within_threshold_are_paired(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0", "1"])
        worker._video_recorder_dictionary = {
            "0": start_recorder(worker, tmp_path, "0"),
            "1": start_recorder(worker, tmp_path, "1"),
        }
        worker._max_frame_bundle_timestamp_delta_ns = 50_000_000

        worker._try_record_synchronized_frame_bundle({
            "0": make_frame_payload("0", 0),
            "1": make_frame_payload("1", 10_000_000),  # 10ms apart -- within threshold
        })

        assert worker._next_frame_index == 1


class TestAbortSemantics:
    def test_partial_submission_then_failure_invalidates_all_outputs(self, worker, tmp_path, monkeypatch):
        """Section 7's required test: camera 2 fails after camera 1 accepts
        the frame. Exact zero-partial-submission is NOT claimed -- see the
        docstring on _try_record_synchronized_frame_bundle -- but the whole
        recording must still end up invalid, with no final files."""
        worker._camera_group = FakeCameraGroup(["0", "1"])
        recorder_0 = start_recorder(worker, tmp_path, "0")
        recorder_1 = start_recorder(worker, tmp_path, "1")
        worker._video_recorder_dictionary = {"0": recorder_0, "1": recorder_1}
        worker._should_record_frames_bool = True

        # Force camera "1"'s append to fail on this bundle, *after* camera
        # "0" has already accepted its frame for the same frame_index --
        # this is the non-atomic ordering the checkpoint flagged.
        from skellycam.opencv.video_recorder.streaming_video_writer import WriterSaturatedError

        original_append = VideoRecorder.append_frame_payload_to_list

        def failing_append(self, frame_payload, frame_index):
            if self is recorder_1:
                raise WriterSaturatedError("simulated saturation on camera 1")
            return original_append(self, frame_payload, frame_index)

        monkeypatch.setattr(VideoRecorder, "append_frame_payload_to_list", failing_append)

        worker._try_record_synchronized_frame_bundle({
            "0": make_frame_payload("0", 0),
            "1": make_frame_payload("1", 0),
        })

        # camera "0" DID accept frame_index 0 before camera "1" failed --
        # confirming submission is not perfectly atomic (as documented) --
        # but the abort must have fired and replaced the whole dictionary.
        assert recorder_0.number_of_frames == 1  # accepted before the failure
        assert worker._should_record_frames_bool is False  # recording stopped

        # the dictionary was replaced with a fresh, empty one by _abort_recording
        assert worker._video_recorder_dictionary["0"] is not recorder_0
        assert worker._video_recorder_dictionary["1"] is not recorder_1
        for fresh_recorder in worker._video_recorder_dictionary.values():
            assert not fresh_recorder.is_streaming

        # and the failed/aborted originals never produced a final file
        assert not (tmp_path / "Camera_0_synchronized.mp4").exists()
        assert not (tmp_path / "Camera_1_synchronized.mp4").exists()

    def test_abort_recording_aborts_every_streaming_recorder(self, worker, tmp_path):
        worker._camera_group = FakeCameraGroup(["0", "1"])
        recorder_0 = start_recorder(worker, tmp_path, "0")
        recorder_1 = start_recorder(worker, tmp_path, "1")
        worker._video_recorder_dictionary = {"0": recorder_0, "1": recorder_1}
        worker._should_record_frames_bool = True

        worker._abort_recording(reason="test")

        assert worker._should_record_frames_bool is False
        # originals were aborted (stop_streaming/abort_streaming already
        # called on them -- calling again would raise) -- verified via the
        # fresh dictionary containing brand new, not-yet-started recorders
        for fresh_recorder in worker._video_recorder_dictionary.values():
            assert not fresh_recorder.is_streaming
