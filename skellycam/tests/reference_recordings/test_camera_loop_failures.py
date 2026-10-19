from contextlib import nullcontext
import logging
import multiprocessing
import threading
import time
from unittest.mock import Mock

import cv2
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
import skellycam.core.camera.opencv.opencv_camera_loop as loop_module
import skellycam.core.camera.opencv.opencv_camera_worker_method as worker_module
from skellycam.core.camera.opencv.opencv_camera_loop import (
    MAX_FAIL_COUNT,
    run_opencv_camera_loop,
)
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import (
    CameraSharedMemoryRingBuffer,
)
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager
from skellycam.tests.reference_recordings.test_capture_reads import frame_buffer


@pytest.mark.parametrize("stop_during_read", [False, True])
def test_failed_reads_never_publish_stale_frames(stop_during_read):
    ipc = Mock(spec=CameraGroupIPC)
    ipc.should_continue = True
    status = CameraStatus()
    status.connected.value = True
    capture = Mock(spec=cv2.VideoCapture)
    capture.isOpened.return_value = True
    orchestrator = Mock(spec=CameraOrchestrator)
    orchestrator.should_grab_by_id.return_value = True
    shm = Mock(spec=CameraSharedMemoryRingBuffer)
    updates = Mock(spec=TopicSubscriptionQueue)
    updates.empty.return_value = True
    recording = Mock(spec=TopicSubscriptionQueue)
    recording.empty.return_value = True
    frame = frame_buffer(64, 48)
    frame.frame_metadata.frame_number[0] = 7
    frame.image[:] = 123

    def fail_grab():
        if stop_during_read:
            ipc.should_continue = False
        return False

    capture.grab.side_effect = fail_grab
    # Bound execution even if a regression reaches publication.
    def unexpected_recording_check(**kwargs):
        raise AssertionError("Failed capture reached recording/publication")

    orchestrator.should_record_frame_number.side_effect = unexpected_recording_check
    outcome = (
        nullcontext()
        if stop_during_read
        else pytest.raises(RuntimeError, match="failed to capture a frame")
    )
    with outcome:
        run_opencv_camera_loop(
            camera_shm=shm,
            config=CameraConfig(camera_id="replay", camera_index=0),
            cv2_video_capture=capture,
            frame_rec_array=frame,
            ipc=ipc,
            orchestrator=orchestrator,
            self_status=status,
            update_camera_settings_subscription=updates,
            recording_info_subscription=recording,
        )

    shm.put_frame.assert_not_called()
    orchestrator.should_record_frame_number.assert_not_called()
    assert capture.grab.call_count == (1 if stop_during_read else MAX_FAIL_COUNT)
    assert frame.frame_metadata.frame_number[0] == 7
    assert not status.grabbing_frame.value
    assert not status.connected.value
    assert status.closed.value
    assert bool(status.error.value) == (not stop_during_read)
    assert not ipc.should_continue


def test_camera_failure_stops_sibling_and_preserves_error(monkeypatch):
    # The application registers custom log methods at startup; this test skips it.
    monkeypatch.setattr(logging.Logger, "trace", logging.Logger.debug, raising=False)
    application_stop = multiprocessing.Value("b", False)
    subscription = Mock(spec=TopicSubscriptionQueue)
    subscription.empty.return_value = True
    ipc = CameraGroupIPC(
        group_id="failure-test",
        pubsub=Mock(spec=PubSubTopicManager),
        extracted_config_subscription=subscription,
        recording_finished_subscription=subscription,
        global_kill_flag=application_stop,
        heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()),
    )
    statuses = {name: CameraStatus() for name in ("failed", "sibling")}
    for status in statuses.values():
        status.connected.value = True
    # The sibling must wait for the failing camera to catch up.
    statuses["sibling"].frame_count.value = 1
    orchestrator = CameraOrchestrator.from_statuses(statuses)
    captures = {name: Mock(spec=cv2.VideoCapture) for name in statuses}
    memories = {
        name: Mock(spec=CameraSharedMemoryRingBuffer) for name in statuses
    }
    sibling_waiting = threading.Event()
    errors = {}

    def synchronization_wait():
        sibling_waiting.set()
        time.sleep(0.001)

    def fail_grab():
        assert sibling_waiting.wait(3), "Sibling never entered the camera loop"
        return False

    captures["failed"].grab.side_effect = fail_grab
    captures["failed"].isOpened.return_value = True
    monkeypatch.setattr(loop_module, "wait_10us", synchronization_wait)

    def setup(**kwargs):
        config = kwargs["config"]
        name = config.camera_id
        return memories[name], config, captures[name], frame_buffer(64, 48)

    monkeypatch.setattr(worker_module, "setup_opencv_camera_loop", setup)

    def run_camera(name):
        try:
            worker_module.opencv_camera_worker_method(
                camera_id=name,
                config=CameraConfig(camera_id=name, camera_index=0),
                ipc=ipc,
                orchestrator=orchestrator,
                update_camera_settings_subscription=subscription,
                shm_subscription=subscription,
                recording_info_subscription=subscription,
            )
        except Exception as error:
            errors[name] = error

    threads = [
        threading.Thread(target=run_camera, args=(name,), daemon=True)
        for name in statuses
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert all(not thread.is_alive() for thread in threads)
        assert set(errors) == {"failed"}, errors
        assert isinstance(errors["failed"], RuntimeError)
        assert "failed to capture a frame" in str(errors["failed"])
        assert ipc.shutdown_camera_group_flag.value
        assert not application_stop.value
        assert statuses["failed"].error.value
        assert not statuses["sibling"].error.value
        assert not orchestrator.all_ready
        captures["sibling"].grab.assert_not_called()
        for name, status in statuses.items():
            assert status.closed.value
            assert not status.connected.value
            assert not status.grabbing_frame.value
            captures[name].release.assert_called_once()
            memories[name].close.assert_called_once()
            memories[name].put_frame.assert_not_called()
    finally:
        ipc.should_continue = False
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=5)
