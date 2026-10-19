"""Real video -> production camera worker/loop -> separately attached shared memory."""

from contextlib import ExitStack, nullcontext
import logging
import multiprocessing
from multiprocessing import shared_memory
import time

import cv2
import numpy as np
import pytest

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.image_resolution import ImageResolution
import skellycam.core.camera.opencv.opencv_camera_loop as loop_module
import skellycam.core.camera.opencv.opencv_camera_worker_method as worker_module
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from skellycam.tests.reference_recordings.datasets import TEST, acquire


@pytest.fixture(scope="module")
def test_videos():
    return acquire(TEST)


@pytest.mark.real_data
@pytest.mark.parametrize("camera_index", [0, 1, 2])
@pytest.mark.parametrize("ending", ["requested-stop", "eof-failure"])
def test_video_camera_loop_publishes_frames_and_cleans_up(test_videos, camera_index, ending, monkeypatch):
    monkeypatch.setattr(logging.Logger, "trace", logging.Logger.debug, raising=False)

    def forbid_hardware_reopen(*args, **kwargs):
        pytest.fail("File replay unexpectedly attempted to reopen a physical camera")

    monkeypatch.setattr(loop_module, "create_cv2_video_capture", forbid_hardware_reopen)
    names = []
    with ExitStack() as cleanup:
        capture = cv2.VideoCapture(str(test_videos[camera_index]), cv2.CAP_FFMPEG)
        cleanup.callback(capture.release)
        baseline = cv2.VideoCapture(str(test_videos[camera_index]), cv2.CAP_FFMPEG)
        cleanup.callback(baseline.release)
        assert capture.isOpened() and baseline.isOpened()
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        assert (width, height) == (720, 1280)
        config = CameraConfig(
            camera_id=f"reference-camera-{camera_index}", camera_index=camera_index,
            resolution=ImageResolution(width=width, height=height),
        )
        frame = np.zeros(1, dtype=create_frame_dtype(config)).view(np.recarray)
        frame.frame_metadata.camera_info = config.to_frame_camera_info()[0]
        frame.frame_metadata.frame_number[0] = -1
        owner = CameraSharedMemoryRingBuffer.create(
            example_data=frame, read_only=False, ring_buffer_length=4,
        )
        cleanup.callback(owner.close_and_unlink)
        dto = owner.to_dto()
        for element in (dto.ring_shm_dto, dto.last_written_index_shm_dto, dto.last_read_index_shm_dto):
            names.extend((element.shm_name, element.shm_valid_name, element.first_written_shm_name))
        writer = CameraSharedMemoryRingBuffer.recreate(dto=dto, read_only=False)
        cleanup.callback(writer.close)
        reader = CameraSharedMemoryRingBuffer.recreate(dto=dto, read_only=False)
        cleanup.callback(reader.close)
        assert owner.ring_buffer_length == 4
        assert not writer.original and not reader.original
        updates = multiprocessing.Queue()
        cleanup.callback(updates.close)
        recording = multiprocessing.Queue()
        cleanup.callback(recording.close)
        ipc = CameraGroupIPC(
            group_id="reference-loop", pubsub=PubSubTopicManager(topics={}),
            extracted_config_subscription=updates, recording_finished_subscription=recording,
            global_kill_flag=multiprocessing.Value("b", False),
            heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()),
        )
        status = CameraStatus()
        status.connected.value = True
        orchestrator = CameraOrchestrator.from_statuses({config.camera_id: status})
        received = []
        paused_ticks = 0
        output = np.zeros_like(frame).view(np.recarray)
        put_frame = writer.put_frame

        def publish_and_observe(frame_rec_array, overwrite):
            put_frame(frame_rec_array=frame_rec_array, overwrite=overwrite)
            actual = reader.retrieve_next_frame(output)
            number = len(received)
            assert owner.last_written_index.value == number
            assert int(actual.frame_metadata.frame_number[0]) == number
            assert actual.frame_metadata.camera_info.camera_id[0] == config.camera_id
            assert int(actual.frame_metadata.camera_info.camera_index[0]) == camera_index
            ok, expected = baseline.read()
            assert ok, f"Baseline ended before published frame {number}"
            # The production capture helper overlays text within the first 80 rows.
            np.testing.assert_array_equal(actual.image[0, 80:], expected[80:])
            stamps = actual.frame_metadata.timestamps
            assert 0 < stamps.pre_frame_grab_ns[0] <= stamps.post_frame_grab_ns[0]
            assert stamps.post_frame_grab_ns[0] <= stamps.pre_frame_retrieve_ns[0]
            assert stamps.pre_frame_retrieve_ns[0] <= stamps.post_frame_retrieve_ns[0]
            assert stamps.post_frame_retrieve_ns[0] <= stamps.pre_copy_to_camera_shm_ns[0]
            received.append(number)
            if number == 10:
                status.should_pause.value = True
            if number == TEST.frames - 1 and ending == "requested-stop":
                status.should_close.value = True

        def observe_pause_and_resume():
            nonlocal paused_ticks
            assert status.is_paused.value
            assert received == list(range(11))
            assert owner.last_written_index.value == 10
            assert int(capture.get(cv2.CAP_PROP_POS_FRAMES)) == 11
            paused_ticks += 1
            if paused_ticks == 3:
                status.should_pause.value = False

        def file_setup(**kwargs):
            assert kwargs["config"] is config
            return writer, config, capture, frame

        # Replace hardware setup and add synchronous observation/control hooks.
        # Capture, loop, orchestration, shared-memory copies and cleanup stay real.
        monkeypatch.setattr(worker_module, "setup_opencv_camera_loop", file_setup)
        monkeypatch.setattr(writer, "put_frame", publish_and_observe)
        monkeypatch.setattr(loop_module, "wait_1ms", observe_pause_and_resume)
        outcome = (
            pytest.raises(RuntimeError, match="failed to capture a frame after 30 attempts")
            if ending == "eof-failure" else nullcontext()
        )
        with outcome:
            worker_module.opencv_camera_worker_method(
                camera_id=config.camera_id, config=config, ipc=ipc, orchestrator=orchestrator,
                update_camera_settings_subscription=updates, shm_subscription=updates,
                recording_info_subscription=recording,
            )
        assert received == list(range(TEST.frames))
        assert paused_ticks == 3
        assert not baseline.read()[0]
        assert owner.last_written_index.value == TEST.frames - 1
        assert owner.last_read_index.value == TEST.frames - 1
        with pytest.raises(IndexError, match="overwritten"):
            reader.get_data_by_index(0)
        assert status.closed.value and not status.connected.value
        assert bool(status.error.value) == (ending == "eof-failure")
        assert ipc.shutdown_camera_group_flag.value and not ipc.global_kill_flag.value
        assert not capture.isOpened()  # Production worker released it, before fallback cleanup.
        for element in (writer.ring_shm, writer.last_written_index, writer.last_read_index):
            assert element.shm.buf is None
            assert element.valid_flag_shm.buf is None
            assert element.first_data_written_shm.buf is None
    assert not baseline.isOpened()
    for name in names:
        try:
            leaked = shared_memory.SharedMemory(name=name)
        except FileNotFoundError:
            continue
        leaked.close()
        pytest.fail(f"Shared-memory allocation leaked: {name}")
