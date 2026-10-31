"""Startup failures must retain their cause and release locally owned resources."""
import logging
import multiprocessing
import time
from queue import Queue
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers import create_cv2_video_capture as creation
from skellycam.core.camera_group.camera_errors import CameraConfigurationError, CameraConnectionCancelled
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager, TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import DeviceExtractedConfigMessage
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.camera.opencv.opencv_helpers import setup_opencv_camera_loop as setup
from skellycam.core.camera_group.camera_group import await_extracted_configs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.types.type_overloads import TopicSubscriptionQueue


@pytest.fixture
def ipc(monkeypatch):
    for name in ("trace", "success"):
        monkeypatch.setattr(logging.Logger, name, logging.Logger.debug, raising=False)
    queue = Mock(spec=TopicSubscriptionQueue, wraps=Queue())
    return CameraGroupIPC(
        group_id="startup-test", pubsub=Mock(spec=PubSubTopicManager, topics={TopicTypes.EXTRACTED_CONFIG: Mock()}),
        extracted_config_subscription=queue, recording_finished_subscription=queue,
        global_kill_flag=multiprocessing.Value("b", False),
        heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()),
    )


async def test_aborted_startup_does_not_validate_missing_config_as_none(ipc):
    ipc.should_continue = False
    config = CameraConfig(camera_id="8752", camera_index=4)
    with pytest.raises(RuntimeError, match="8752"):
        await await_extracted_configs(ipc, {config.camera_id: config})


def test_setup_releases_capture_when_sibling_aborts_before_shared_memory(monkeypatch, ipc):
    capture = Mock()
    config = CameraConfig(camera_id="3e59", camera_index=1)
    monkeypatch.setattr(setup, "create_cv2_video_capture", lambda config, **kwargs: (capture, config))
    monkeypatch.setattr(setup, "logger", Mock())
    ipc.should_continue = False
    with pytest.raises(setup.CameraSetupFailedException):
        setup.setup_opencv_camera_loop(
            camera_shm=None, config=config, ipc=ipc, orchestrator=Mock(spec=CameraOrchestrator),
            self_status=CameraStatus(), shm_subscription=Mock(spec=TopicSubscriptionQueue),
        )
    capture.release.assert_called_once()
    assert not ipc.failure_message


@pytest.fixture
def capture(monkeypatch):
    capture = Mock(spec=cv2.VideoCapture)
    capture.isOpened.return_value = True
    capture.set.return_value = False
    capture.read.return_value = (True, np.zeros((2, 2, 3), dtype=np.uint8))
    monkeypatch.setattr(creation.cv2, "VideoCapture", Mock(return_value=capture))
    monkeypatch.setattr(creation, "wait_1s", lambda: None)
    return capture


@pytest.mark.parametrize("failure", ["open", "read", "configure"])
def test_failed_connection_releases_each_capture_and_names_device(capture, monkeypatch, failure):
    config = CameraConfig(camera_id="8752", camera_index=4)
    if failure == "open":
        capture.isOpened.return_value = False
        expected = creation.FailedToOpenCameraException
    elif failure == "read":
        capture.read.return_value = (False, None)
        expected = creation.FailedToReadFrameFromCameraException
    else:
        monkeypatch.setattr(creation, "apply_camera_configuration", Mock(side_effect=ValueError("invalid properties")))
        expected = ValueError
    with pytest.raises(expected) as caught:
        creation.create_cv2_video_capture(config, retry_count=1)
    assert capture.release.call_count == (1 if failure == "configure" else 2)
    if failure != "configure":
        assert "8752" in str(caught.value) and "index 4" in str(caught.value)


def test_successful_capture_transfers_ownership(capture, monkeypatch):
    config = CameraConfig(camera_id="7599", camera_index=2)
    monkeypatch.setattr(creation, "apply_camera_configuration", lambda **kwargs: config)
    assert creation.create_cv2_video_capture(config) == (capture, config)
    capture.release.assert_not_called()


def test_cancelled_retry_does_not_reopen_camera(capture):
    capture.read.return_value = (False, None)
    checks = iter([True, True, False])
    with pytest.raises(CameraConnectionCancelled):
        creation.create_cv2_video_capture(
            CameraConfig(camera_id="8752", camera_index=4), should_continue=lambda: next(checks)
        )
    capture.release.assert_called_once()
    creation.cv2.VideoCapture.assert_called_once()


async def test_invalid_device_properties_reach_parent_without_none_config(capture, ipc):
    config = CameraConfig(camera_id="ef51", camera_index=0)
    # Exercise the real create -> apply -> extract -> setup -> parent path.
    capture.get.return_value = 0.0
    with pytest.raises(setup.CameraSetupFailedException):
        setup.setup_opencv_camera_loop(
            camera_shm=None, config=config, ipc=ipc, orchestrator=Mock(spec=CameraOrchestrator),
            self_status=CameraStatus(), shm_subscription=Mock(spec=TopicSubscriptionQueue),
        )
    # The first requested camera is NOT the camera that caused the failure.
    other = CameraConfig(camera_id="8752", camera_index=4)
    with pytest.raises(CameraConfigurationError, match="ef51.*index 0.*width=0, height=0"):
        await await_extracted_configs(ipc, {other.camera_id: other, config.camera_id: config})
    assert "NoneType" not in ipc.failure_message
    capture.release.assert_called_once()
    assert not ipc.global_kill_flag.value


def test_setup_closes_shared_memory_if_initial_frame_creation_fails(monkeypatch, ipc):
    config = CameraConfig(camera_id="7599", camera_index=2)
    capture = Mock(spec=cv2.VideoCapture)
    shm = Mock(spec=CameraSharedMemoryRingBuffer, valid=True)
    monkeypatch.setattr(setup, "create_cv2_video_capture", lambda *args, **kwargs: (capture, config))
    monkeypatch.setattr(setup, "create_initial_frame_rec_array", Mock(side_effect=ValueError("frame allocation failed")))
    with pytest.raises(setup.CameraSetupFailedException, match="frame allocation failed"):
        setup.setup_opencv_camera_loop(
            camera_shm=shm, config=config, ipc=ipc,
            orchestrator=Mock(spec=CameraOrchestrator, all_ready=True),
            self_status=CameraStatus(), shm_subscription=Mock(spec=TopicSubscriptionQueue),
        )
    capture.release.assert_called_once()
    shm.close.assert_called_once()
    assert "creating initial frame" in ipc.failure_message


async def test_successful_configs_are_returned_without_placeholders(ipc):
    config = CameraConfig(camera_id="7599", camera_index=2)
    ipc.extracted_config_subscription.put(DeviceExtractedConfigMessage(config))
    assert await await_extracted_configs(ipc, {config.camera_id: config}) == {config.camera_id: config}


async def test_config_wait_has_bounded_timeout(ipc):
    config = CameraConfig(camera_id="8752", camera_index=4)
    with pytest.raises(CameraConfigurationError, match="Timed out.*8752"):
        await await_extracted_configs(ipc, {config.camera_id: config}, timeout_seconds=0.0)
    assert not ipc.should_continue


def test_first_failure_is_not_overwritten_by_sibling_cleanup(ipc):
    ipc.report_camera_failure("ef51", 0, "configuration", ValueError("width=0"))
    ipc.report_camera_failure("8752", 4, "shared memory", RuntimeError("group stopped"))
    assert "ef51" in ipc.failure_message
    assert "8752" not in ipc.failure_message


def report_failure_from_child(ipc):
    ipc.report_camera_failure("ef51", 0, "configuration", ValueError("width=0, height=0"))


async def test_spawned_worker_failure_is_available_when_shutdown_flag_changes():
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    ipc = CameraGroupIPC(
        group_id="spawn-startup-test", pubsub=PubSubTopicManager(topics={}),
        extracted_config_subscription=queue, recording_finished_subscription=queue,
        global_kill_flag=context.Value("b", False),
        heartbeat_timestamp=context.Value("d", time.perf_counter()),
    )
    process = context.Process(target=report_failure_from_child, args=(ipc,))
    try:
        process.start()
        process.join(timeout=10)
        assert process.exitcode == 0
        assert ipc.shutdown_camera_group_flag.value
        config = CameraConfig(camera_id="ef51", camera_index=0)
        with pytest.raises(CameraConfigurationError, match="ef51.*width=0, height=0"):
            await await_extracted_configs(ipc, {config.camera_id: config})
        assert not ipc.global_kill_flag.value
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        if process.pid is not None:
            process.close()
        queue.close()
        queue.join_thread()


async def test_wrong_camera_response_is_rejected(ipc):
    expected = CameraConfig(camera_id="8752", camera_index=4)
    wrong = CameraConfig(camera_id="ef51", camera_index=0)
    ipc.extracted_config_subscription.put(DeviceExtractedConfigMessage(wrong))
    with pytest.raises(CameraConfigurationError, match="unexpected camera ef51"):
        await await_extracted_configs(ipc, {expected.camera_id: expected})


def test_cleanup_error_does_not_mask_configuration_error(capture, monkeypatch):
    capture.release.side_effect = RuntimeError("driver release failed")
    monkeypatch.setattr(creation, "apply_camera_configuration", Mock(side_effect=ValueError("width=0")))
    with pytest.raises(ValueError, match="width=0"):
        creation.create_cv2_video_capture(CameraConfig(camera_id="ef51", camera_index=0))
