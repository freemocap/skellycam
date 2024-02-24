import numpy as np

from skellycam.backend.controller.core_functionality.camera_group.video_recorder.timestamps.timestamp_logger import (
    CameraTimestampLogger,
)
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.models.cameras.frames.frame_payload import FramePayload


def create_dummy_frame_payload(camera_id):
    # Create a dummy 10x20x3 numpy array to simulate an image
    dummy_image = np.zeros((10, 20, 3), dtype=np.uint8)
    timestamp_ns = 123456789
    frame_number = 1
    success = True

    # Create the FramePayload using the classmethod
    dummy_payload = FramePayload.create(
        success=success,
        image=dummy_image,
        timestamp_ns=timestamp_ns,
        frame_number=frame_number,
        camera_id=camera_id,
    )

    return dummy_payload


def test_camera_timestamp_logger_initialization():
    # Arrange
    test_directory = "test_directory"
    test_camera_id = CameraId(1)

    # Act
    logger = CameraTimestampLogger(
        main_timestamps_directory=test_directory, camera_id=test_camera_id
    )

    # Assert
    assert logger.camera_id == test_camera_id
    assert logger._save_directory == test_directory


def test_logging_timestamps():
    # Arrange
    test_directory = "test_directory"
    test_camera_id = CameraId(1)
    logger = CameraTimestampLogger(
        main_timestamps_directory=test_directory, camera_id=test_camera_id
    )
    test_frame_payload = create_dummy_frame_payload(test_camera_id)
    logger.set_time_mapping(perf_counter_to_unix_mapping=(0, 0))

    # Act
    log = logger.log_timestamp(multi_frame_number=1, frame=test_frame_payload)

    # Assert
    assert log.perf_counter_ns_timestamp == test_frame_payload.timestamp_ns
    assert len(logger._timestamp_logs) == 1
    # Add more asserts to validate the logged data
