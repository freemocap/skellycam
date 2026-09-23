"""Concurrent real-video camera loops with production synchronization and shared memory."""

import asyncio
from contextlib import ExitStack
import logging
import multiprocessing
from multiprocessing import shared_memory
import threading
import time
from pathlib import Path

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
from skellycam.core.ipc.pubsub.pubsub_manager import PubSubTopicManager, TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import RecordingFinishedTopic, RecordingInfoMessage
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.fourcc_codec_helpers import PYAV_H264_FOURCC
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from skellycam.tests.reference_recordings.datasets import TEST, acquire


async def wait_until(predicate, errors, description):
    deadline = time.monotonic() + 30
    while not predicate():
        assert not errors, errors
        assert time.monotonic() < deadline, f"Timed out: {description}"
        await asyncio.sleep(0.005)


@pytest.mark.real_data
@pytest.mark.parametrize("fail_camera", [False, True], ids=["complete", "one-camera-eof"])
async def test_concurrent_replay_pause_and_group_shutdown(monkeypatch, fail_camera):
    await run_concurrent_replay(monkeypatch, fail_camera)


async def run_concurrent_replay(monkeypatch, fail_camera, recording_directory=None):
    paths = acquire(TEST)
    monkeypatch.setattr(logging.Logger, "trace", logging.Logger.debug, raising=False)

    def forbid_hardware_reopen(*args, **kwargs):
        raise AssertionError("File replay attempted to reopen a physical camera")

    monkeypatch.setattr(loop_module, "create_cv2_video_capture", forbid_hardware_reopen)
    names = []
    with ExitStack() as cleanup:
        queues = [multiprocessing.Queue() for _ in range(6)]
        for queue in queues:
            cleanup.callback(queue.close)
        finished_topic = RecordingFinishedTopic()
        finished_queue = finished_topic.get_subscription()
        cleanup.callback(finished_topic.close)
        ipc = CameraGroupIPC(
            group_id="concurrent-reference",
            pubsub=PubSubTopicManager(topics={TopicTypes.RECORDING_FINISHED: finished_topic}),
            extracted_config_subscription=queues[0], recording_finished_subscription=finished_queue,
            global_kill_flag=multiprocessing.Value("b", False),
            heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()),
        )
        statuses = {str(index): CameraStatus() for index in range(3)}
        for status in statuses.values():
            status.connected.value = True
        orchestrator = CameraOrchestrator.from_statuses(statuses)
        recording_info = None
        if recording_directory is not None:
            recording_info = RecordingInfo(recording_name="replay", recording_directory=str(recording_directory))
            orchestrator.first_recording_frame_number.value = 0
            for queue in queues[1::2]:
                queue.put(RecordingInfoMessage(recording_info=recording_info))
            await wait_until(lambda: all(not queue.empty() for queue in queues[1::2]), {}, "recording requests")
        cameras = {}
        received = {camera_id: [] for camera_id in statuses}
        errors = {}
        progress_lock = threading.Lock()
        failure_requested = threading.Event()
        finish = threading.Event()

        def prepare_camera(index, path):
            camera_id = str(index)
            capture = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
            cleanup.callback(capture.release)
            baseline = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG)
            cleanup.callback(baseline.release)
            assert capture.isOpened() and baseline.isOpened()
            config = CameraConfig(
                camera_id=camera_id, camera_index=index,
                resolution=ImageResolution(width=720, height=1280),
                framerate=6.0, writer_fourcc=PYAV_H264_FOURCC,
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
            output = np.zeros_like(frame).view(np.recarray)
            real_put = writer.put_frame

            def publish_and_observe(frame_rec_array, overwrite):
                real_put(frame_rec_array=frame_rec_array, overwrite=overwrite)
                actual = reader.retrieve_next_frame(output)
                number = len(received[camera_id])
                assert int(actual.frame_metadata.frame_number[0]) == number
                assert actual.frame_metadata.camera_info.camera_id[0] == camera_id
                assert int(actual.frame_metadata.camera_info.camera_index[0]) == index
                ok, expected = baseline.read()
                assert ok
                np.testing.assert_array_equal(actual.image[0, 80:], expected[80:])
                # Unequal work per camera exercises the real orchestrator's pacing.
                if index == 2:
                    time.sleep(0.003)
                with progress_lock:
                    received[camera_id].append(number)
                    counts = [len(frames) for frames in received.values()]
                    assert max(counts) - min(counts) <= 1, counts
                if camera_id == "0" and failure_requested.is_set():
                    # Seek this real capture to EOF; siblings retain unread frames.
                    assert capture.set(cv2.CAP_PROP_POS_FRAMES, TEST.frames)
                    failure_requested.clear()
                if number == TEST.frames - 1:
                    # Only the final frame waits for controller shutdown. There is
                    # no test barrier between ordinary frames or between cameras.
                    assert finish.wait(10), "Controller did not finish replay"

            monkeypatch.setattr(writer, "put_frame", publish_and_observe)
            return config, capture, baseline, frame, owner, writer

        for index, path in enumerate(paths):
            cameras[str(index)] = prepare_camera(index, path)

        def file_setup(**kwargs):
            config, capture, _, frame, _, writer = cameras[kwargs["config"].camera_id]
            return writer, config, capture, frame

        monkeypatch.setattr(worker_module, "setup_opencv_camera_loop", file_setup)

        def run_camera(camera_id):
            try:
                index = int(camera_id)
                worker_module.opencv_camera_worker_method(
                    camera_id=camera_id, config=cameras[camera_id][0], ipc=ipc,
                    orchestrator=orchestrator,
                    update_camera_settings_subscription=queues[2 * index],
                    shm_subscription=queues[2 * index],
                    recording_info_subscription=queues[2 * index + 1],
                )
            except BaseException as error:
                # Observe only: the production worker must signal group shutdown.
                errors[camera_id] = error

        threads = [threading.Thread(target=run_camera, args=(key,), daemon=True) for key in cameras]

        def stop_and_join():
            ipc.should_continue = False
            finish.set()
            deadline = time.monotonic() + 10
            for thread in threads:
                if thread.ident is not None:
                    thread.join(timeout=max(0, deadline - time.monotonic()))
            assert all(not thread.is_alive() for thread in threads), "Camera thread survived shutdown"

        # Stop/join before closing buffers, including when an assertion fails.
        cleanup.callback(stop_and_join)
        for thread in threads:
            thread.start()
        await wait_until(lambda: min(map(len, received.values())) >= 20, errors, "initial frames")
        await asyncio.wait_for(orchestrator.pause(), timeout=5)
        assert all(thread.is_alive() for thread in threads)
        before = [(item[4].last_written_index.value, item[1].get(cv2.CAP_PROP_POS_FRAMES))
                  for item in cameras.values()]
        await asyncio.sleep(0.05)
        after = [(item[4].last_written_index.value, item[1].get(cv2.CAP_PROP_POS_FRAMES))
                 for item in cameras.values()]
        assert before == after
        assert orchestrator.all_cameras_paused
        await asyncio.wait_for(orchestrator.unpause(), timeout=5)
        await wait_until(lambda: min(map(len, received.values())) >= 60, errors, "resumed frames")
        if fail_camera:
            failure_requested.set()
            await wait_until(lambda: not any(t.is_alive() for t in threads), {}, "failure shutdown")
            assert set(errors) == {"0"}, errors
            assert isinstance(errors["0"], RuntimeError)
            assert "failed to capture a frame after 30 attempts" in str(errors["0"])
            assert all(60 <= len(frames) < TEST.frames for frames in received.values())
        else:
            await wait_until(lambda: all(len(frames) == TEST.frames for frames in received.values()),
                             errors, "complete replay")
            stop_and_join()
            assert not errors
            assert all(not item[2].read()[0] for item in cameras.values())
        assert not any(t.is_alive() for t in threads)
        assert ipc.shutdown_camera_group_flag.value and not ipc.global_kill_flag.value
        if recording_info is not None:
            messages = [finished_queue.get(timeout=5) for _ in cameras]
            assert {message.camera_id for message in messages} == set(cameras)
            for message in messages:
                camera_id = message.camera_id
                assert [int(md.frame_number[0]) for md in message.frame_metadatas] == received[camera_id]
                config = cameras[camera_id][0]
                video_path = recording_info.video_file_path_from_camera_config(config)
                assert Path(video_path).is_file()
                saved = cv2.VideoCapture(video_path)
                source = cv2.VideoCapture(str(paths[int(camera_id)]))
                try:
                    assert saved.isOpened() and source.isOpened()
                    for number in received[camera_id]:
                        ok, actual = saved.read()
                        source_ok, expected = source.read()
                        assert ok and source_ok, f"Finalized camera {camera_id} lost frame {number}"
                        difference = np.abs(actual[80:].astype(np.int16) - expected[80:].astype(np.int16))
                        assert float(difference.mean()) < 8, (camera_id, number)
                    assert not saved.read()[0]
                finally:
                    saved.release()
                    source.release()
        for camera_id, (_, capture, _, _, owner, writer) in cameras.items():
            frames = received[camera_id]
            assert frames == list(range(len(frames)))
            assert owner.last_written_index.value == len(frames) - 1
            assert owner.last_read_index.value == len(frames) - 1
            status = statuses[camera_id]
            assert status.closed.value and not status.connected.value
            assert bool(status.error.value) == (fail_camera and camera_id == "0")
            assert not capture.isOpened()
            for element in (writer.ring_shm, writer.last_written_index, writer.last_read_index):
                assert element.shm.buf is None
                assert element.valid_flag_shm.buf is None
                assert element.first_data_written_shm.buf is None
    assert len(names) == 27
    for name in names:
        try:
            leaked = shared_memory.SharedMemory(name=name)
        except FileNotFoundError:
            continue
        leaked.close()
        pytest.fail(f"Shared-memory allocation leaked: {name}")
