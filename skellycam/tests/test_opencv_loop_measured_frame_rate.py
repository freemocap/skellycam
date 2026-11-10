"""A recording declares the camera's measured frame rate; a frame-rate change must restart that measurement.

The OpenCV camera loop measures its delivered rate as the median of recent frame intervals and passes it to
the video recorder it creates. After an in-place frame-rate change, intervals from the previous stream would
otherwise dominate that median for hundreds of frames and the next recording would declare the old rate.
"""
from unittest.mock import Mock

import cv2
import pytest

import skellycam.core.camera.opencv.opencv_camera_loop as loop_module
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.tests.reference_recordings.test_capture_reads import frame_buffer

REPORTED_30_FPS = 1e7 / 333333
REPORTED_60_FPS = 1e7 / 166666
CHANGE_AT = 40  # loop iteration whose settings update changes the camera
STOP_AT = 75


@pytest.mark.parametrize("change, measurement_restarts", [
    ({"framerate": REPORTED_60_FPS}, True),
    ({"exposure": -5}, False),
])
def test_frame_rate_change_restarts_the_measured_rate(monkeypatch, change, measurement_restarts):
    ipc = Mock(spec=CameraGroupIPC)
    ipc.should_continue = True
    status = CameraStatus()
    status.connected.value = True
    capture = Mock(spec=cv2.VideoCapture)
    capture.isOpened.return_value = True
    orchestrator = Mock(spec=CameraOrchestrator)
    orchestrator.should_grab_by_id.return_value = True
    orchestrator.should_record_frame_number.return_value = (False, False)
    frame = frame_buffer(64, 48)
    rates_offered_to_recorder = []

    def update_checks(*, config, frame_rec_array, video_recorder, self_status, framerate, **_):
        rates_offered_to_recorder.append(framerate)
        if len(rates_offered_to_recorder) == CHANGE_AT:
            config = config.model_copy(update=change)
        if len(rates_offered_to_recorder) == STOP_AT:
            ipc.should_continue = False
        return config, frame_rec_array, video_recorder, self_status

    monkeypatch.setattr(loop_module, "camera_loop_update_checks", update_checks)
    monkeypatch.setattr(loop_module, "opencv_get_frame", lambda cap, frame_rec_array: (True, frame_rec_array))
    monkeypatch.setattr(loop_module, "handle_video_recording", lambda **kwargs: kwargs["video_recorder"])
    loop_module.run_opencv_camera_loop(
        camera_shm=Mock(spec=CameraSharedMemoryRingBuffer),
        config=CameraConfig(camera_id="cam", camera_index=0, framerate=REPORTED_30_FPS),
        cv2_video_capture=capture, frame_rec_array=frame, ipc=ipc, orchestrator=orchestrator,
        self_status=status, update_camera_settings_subscription=Mock(spec=TopicSubscriptionQueue),
        recording_info_subscription=Mock(spec=TopicSubscriptionQueue))

    assert rates_offered_to_recorder[CHANGE_AT - 1] is not None  # measured from 30+ frames of the old stream
    assert (rates_offered_to_recorder[CHANGE_AT] is None) is measurement_restarts
    assert rates_offered_to_recorder[CHANGE_AT + 30] is not None  # measured again from the new stream

