"""Active video writers take priority over automatic termination deadlines."""

import multiprocessing
import threading
import time
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

from skellycam.core.ipc.process_management.managed_worker import ManagedProcess, WorkerMode
from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.camera.camera_worker import CameraWorker
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.camera.opencv.opencv_helpers.handle_recording_updates import finish_recording
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.recorders.videos.fourcc_codec_helpers import PYAV_H264_FOURCC
from skellycam.core.recorders.videos.pyav_video_writer import PyavVideoWriter
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.tests.reference_recordings.test_capture_reads import frame_buffer


def save_before_exit(*, path, stop, saving, ready, allow_finish):
    writer = PyavVideoWriter(path=path, fps=6.0, width=64, height=48)
    try:
        for index in range(8):
            writer.write(np.full((48, 64, 3), index * 25, dtype=np.uint8))
        ready.set()
        while not stop.value:
            time.sleep(0.005)
        if not allow_finish.wait(15):
            raise RuntimeError("Test did not release the save gate")
    finally:
        writer.release()
        saving.value = False


@pytest.mark.parametrize("method", ["terminate", "kill", "terminate_gracefully"])
def test_force_shutdown_waits_for_real_video_finalization(tmp_path, method):
    stop = multiprocessing.Value("b", False)
    saving = multiprocessing.Value("b", True)
    ready = multiprocessing.Event()
    allow_finish = multiprocessing.Event()
    path = tmp_path / "protected.mp4"
    worker = ManagedProcess(
        target=save_before_exit, name="protected-video", shutdown_flag=stop,
        log_queue=None, daemon=False,
        kwargs=dict(path=str(path), stop=stop, saving=saving, ready=ready, allow_finish=allow_finish),
    )
    worker.protect_recording(saving)
    errors = []

    def request_stop():
        try:
            getattr(worker, method)()
        except BaseException as error:
            errors.append(error)

    shutdown = threading.Thread(target=request_stop, daemon=True)
    worker.start()
    try:
        assert ready.wait(15), "Writer did not start"
        shutdown.start()
        deadline = time.monotonic() + 5
        while not stop.value and time.monotonic() < deadline:
            time.sleep(0.005)
        assert stop.value
        assert saving.value and worker.is_alive() and shutdown.is_alive()
        allow_finish.set()
        shutdown.join(timeout=10)
        worker.join(timeout=10.0)
        assert not shutdown.is_alive() and not worker.is_alive()
        assert not errors
        assert not saving.value
        capture = cv2.VideoCapture(str(path))
        try:
            assert capture.isOpened()
            for index in range(8):
                ok, image = capture.read()
                assert ok, f"Finalized video lost frame {index}"
                assert abs(float(image.mean()) - index * 25) < 6
            assert not capture.read()[0]
        finally:
            capture.release()
    finally:
        stop.value = True
        allow_finish.set()
        worker.join(timeout=20.0)
        if shutdown.ident is not None:
            shutdown.join(timeout=10)
        # Do not force-kill a saving worker, even from test cleanup.
        assert not worker.is_alive(), "Writer survived cooperative test cleanup"
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("failure", ["encode", "mux"])
def test_pyav_attempts_container_close_after_flush_failure(failure):
    writer = object.__new__(PyavVideoWriter)
    writer._open = True
    writer._stream = Mock()
    writer._container = Mock()
    if failure == "encode":
        writer._stream.encode.side_effect = RuntimeError("flush failed")
    else:
        writer._stream.encode.return_value = [object()]
        writer._container.mux.side_effect = RuntimeError("flush failed")
    with pytest.raises(RuntimeError, match="flush failed"):
        writer.release()
    writer._container.close.assert_called_once()
    assert not writer.isOpened()
    writer.release()
    writer._container.close.assert_called_once()


def test_server_shutdown_waits_for_video_saves():
    application_stop = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=application_stop, worker_mode=WorkerMode.THREAD)
    worker = Mock()
    worker.pid = None
    worker.is_alive.return_value = False
    waiting = threading.Event()
    finished = threading.Event()

    def finish_save():
        waiting.set()
        assert finished.wait(10), "Test did not release finalization"

    worker.wait_for_recording_save.side_effect = finish_save
    registry._workers.append(worker)
    with patch("skellycam.core.ipc.process_management.worker_registry.os.kill") as terminate_server:
        registry.start_heartbeat()
        try:
            application_stop.value = True
            assert waiting.wait(5)
            terminate_server.assert_not_called()
            finished.set()
            deadline = time.monotonic() + 5
            while not terminate_server.called and time.monotonic() < deadline:
                time.sleep(0.005)
            terminate_server.assert_called_once()
        finally:
            finished.set()
            registry.shutdown_all()


def test_camera_worker_registers_save_protection():
    status = CameraStatus()
    orchestrator = CameraOrchestrator.from_statuses({"camera": status})
    ipc = Mock(spec=CameraGroupIPC)
    ipc.pubsub = Mock()
    ipc.pubsub.topics = {TopicTypes.LOGS: Mock()}
    ipc.shutdown_camera_group_flag = multiprocessing.Value("b", False)
    registry = Mock(spec=WorkerRegistry)
    registry.worker_mode = WorkerMode.PROCESS
    worker = Mock(spec=ManagedWorker)
    registry.create_worker.return_value = worker
    queue = Mock(spec=TopicSubscriptionQueue)
    CameraWorker.create(
        camera_id="camera", ipc=ipc, worker_registry=registry,
        config=CameraConfig(camera_id="camera", camera_index=0), orchestrator=orchestrator,
        update_camera_settings_subscription=queue, shm_subscription=queue,
        recording_info_subscription=queue,
    )
    worker.protect_recording.assert_called_once_with(status.recording_in_progress)
    assert registry.create_worker.call_args.kwargs["daemon"] is False


def test_notification_failure_does_not_prevent_video_finalization(tmp_path):
    info = RecordingInfo(recording_name="notification-failure", recording_directory=str(tmp_path))
    config = CameraConfig(
        camera_id="replay", camera_index=0, resolution=ImageResolution(width=64, height=48),
        writer_fourcc=PYAV_H264_FOURCC, framerate=6.0,
    )
    recorder = VideoRecorder.create(recording_info=info, config=config)
    ipc = Mock(spec=CameraGroupIPC)
    ipc.pubsub = Mock()
    notification = Mock()
    notification.publish.side_effect = RuntimeError("notification failed")
    ipc.pubsub.topics = {TopicTypes.RECORDING_FINISHED: notification}
    try:
        frame = frame_buffer(64, 48)
        for number in range(8):
            frame.frame_metadata.frame_number[0] = number
            frame.image[:] = number * 25
            recorder.record_frame(frame)
        with pytest.raises(RuntimeError, match="notification failed"):
            finish_recording(ipc=ipc, video_recorder=recorder)
        assert recorder.video_writer is None
        capture = cv2.VideoCapture(recorder.video_file_path)
        try:
            assert capture.isOpened()
            for number in range(8):
                ok, image = capture.read()
                assert ok
                assert abs(float(image.mean()) - number * 25) < 6
            assert not capture.read()[0]
        finally:
            capture.release()
    finally:
        recorder.close()
        from pathlib import Path
        Path(recorder.video_file_path).unlink(missing_ok=True)
