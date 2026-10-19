"""Startup aborts must preserve the worker error across the process boundary."""
import asyncio
import multiprocessing
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import await_extracted_configs
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC

from skellycam.core.camera_group.camera_setup_failure import CameraSetupFailure, CameraSetupFailedException
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager
from skellycam.core.ipc.pubsub.pubsub_topics import DeviceExtractedConfigMessage
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry


def test_aborted_startup_reports_missing_camera_instead_of_type_error():
    ipc = Mock(spec=CameraGroupIPC, should_continue=False)
    ipc.take_setup_failure.return_value = None
    with pytest.raises(RuntimeError, match='1622'):
        asyncio.run(await_extracted_configs(
            ipc=ipc, requested_configs={'1622': CameraConfig(camera_id='1622', camera_index=0)}))



@pytest.fixture
def ipc():
    value = CameraGroupIPC(
        group_id='test', pubsub=PubSubTopicManager(topics={}),
        extracted_config_subscription=multiprocessing.Queue(),
        recording_finished_subscription=multiprocessing.Queue(),
        global_kill_flag=multiprocessing.Value('b', False),
        heartbeat_timestamp=multiprocessing.Value('d', time.perf_counter()),
    )
    yield value
    value.setup_failures.close()
    value.extracted_config_subscription.close()
    value.extracted_config_subscription.join_thread()
    value.recording_finished_subscription.close()
    value.recording_finished_subscription.join_thread()


def _worker_reports_failure(ipc):
    ipc.report_setup_failure(CameraSetupFailure('1622', 'opening camera', 'FailedToOpenCameraException', 'access denied'))
    ipc.report_setup_failure(CameraSetupFailure('sibling', 'shared memory', 'RuntimeError', 'group stopped'))


def test_spawned_worker_failure_survives_shutdown(ipc):
    process = multiprocessing.Process(target=_worker_reports_failure, args=(ipc,))
    process.start()
    try:
        process.join(15)
        assert process.exitcode == 0
        assert not ipc.global_kill_flag.value
        with pytest.raises(CameraSetupFailedException, match='Camera 1622.*opening camera.*FailedToOpenCameraException: access denied'):
            asyncio.run(await_extracted_configs(ipc=ipc, requested_configs={'1622': CameraConfig(camera_id='1622', camera_index=0)}))
    finally:
        if process.is_alive():
            process.terminate()
            process.join()


def test_successful_config_is_unchanged(ipc):
    config = CameraConfig(camera_id='1622', camera_index=0)
    ipc.extracted_config_subscription.put(DeviceExtractedConfigMessage(config))
    result = asyncio.run(asyncio.wait_for(await_extracted_configs(ipc=ipc, requested_configs={'1622': config}), 2))
    assert result == {'1622': config}


def test_failed_group_cleanup_preserves_failure_and_allows_retry():
    registry = Mock(spec=WorkerRegistry)
    registry.heartbeat_timestamp = multiprocessing.Value('d', time.perf_counter())
    manager = CameraGroupManager(global_kill_flag=multiprocessing.Value('b', False), worker_registry=registry)
    failed = Mock(spec=CameraGroup, id='failed', ipc=Mock())
    failed.ipc.pubsub.get_subscription.return_value = multiprocessing.Queue()
    failure = CameraSetupFailedException('Camera 1622 failed opening: access denied')
    failed.start = AsyncMock(side_effect=failure)
    failed.close = AsyncMock()
    healthy = Mock(spec=CameraGroup, id='retry', ipc=Mock(), camera_ids=['1622'])
    healthy.ipc.pubsub.get_subscription.return_value = multiprocessing.Queue()
    healthy.start = AsyncMock()
    configs = {'1622': CameraConfig(camera_id='1622', camera_index=0)}
    try:
        with patch.object(CameraGroup, 'create', side_effect=[failed, healthy]):
            with pytest.raises(CameraSetupFailedException) as caught:
                asyncio.run(manager.create_and_start_camera_group(configs))
            assert caught.value is failure
            failed.close.assert_awaited_once()
            assert not manager.camera_groups
            assert not manager.camera_group_framerate_subscriptions
            assert asyncio.run(manager.create_and_start_camera_group(configs)) is healthy
    finally:
        failed.ipc.pubsub.get_subscription.return_value.close()
        healthy.ipc.pubsub.get_subscription.return_value.close()


def test_worker_setup_reports_original_open_error(ipc):
    from skellycam.core.camera.opencv.opencv_helpers.setup_opencv_camera_loop import setup_opencv_camera_loop
    from skellycam.core.camera.opencv.opencv_helpers.create_cv2_video_capture import FailedToOpenCameraException
    from skellycam.core.camera_group.camera_status import CameraStatus
    from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
    config = CameraConfig(camera_id='1622', camera_index=0)
    status = CameraStatus()
    with patch('skellycam.core.camera.opencv.opencv_helpers.setup_opencv_camera_loop.create_cv2_video_capture',
               side_effect=FailedToOpenCameraException('camera access denied')):
        with pytest.raises(CameraSetupFailedException, match='FailedToOpenCameraException: camera access denied'):
            setup_opencv_camera_loop(camera_shm=None, config=config, ipc=ipc,
                                     orchestrator=Mock(spec=CameraOrchestrator), self_status=status,
                                     shm_subscription=ipc.extracted_config_subscription)
    assert status.error.value
    assert not ipc.global_kill_flag.value
    with pytest.raises(CameraSetupFailedException, match='1622.*FailedToOpenCameraException: camera access denied'):
        asyncio.run(await_extracted_configs(ipc=ipc, requested_configs={'1622': config}))


def test_exhausted_open_retries_report_device_backend_and_release_capture():
    from skellycam.core.camera.opencv.opencv_helpers.create_cv2_video_capture import create_cv2_video_capture, FailedToOpenCameraException
    from skellycam.core.camera.determine_backend import OpenCVBackend
    class ClosedCapture:
        release = Mock()

        def __init__(self, *args):
            pass

        def isOpened(self):
            return False

    with patch('skellycam.core.camera.opencv.opencv_helpers.create_cv2_video_capture.cv2.VideoCapture', ClosedCapture), \
         patch('skellycam.core.camera.opencv.opencv_helpers.create_cv2_video_capture.determine_opencv_camera_backend',
               return_value=OpenCVBackend(1200, 'AVFOUNDATION')):
        with pytest.raises(FailedToOpenCameraException, match='1622.*index 0.*AVFOUNDATION.*1 attempts'):
            create_cv2_video_capture(CameraConfig(camera_id='1622', camera_index=0), retry_count=0)
    ClosedCapture.release.assert_called_once()


def test_verbose_failure_is_bounded_and_does_not_block_shutdown(ipc):
    ipc.report_setup_failure(CameraSetupFailure('1622', 'opening camera', 'RuntimeError', '💀' * 100000))
    failure = ipc.take_setup_failure()
    assert failure.camera_id == '1622'
    assert len(failure.message) == 512
    assert not ipc.should_continue
    assert not ipc.global_kill_flag.value
