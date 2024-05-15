import numpy as np

from skellycam.core import CameraId
from skellycam.core.frames.frame_payload import FramePayload
from skellycam.core.timestamps.timestamp_logger import CameraTimestampLogger


def test_camera_timestamp_logger_initialization():
    # Arrange
    test_directory = "test_directory"
    test_camera_id = CameraId(1)

    # Act
    timestamp_logger = CameraTimestampLogger(
        main_timestamps_directory=test_directory, camera_id=test_camera_id
    )

    # Assert
    assert timestamp_logger.camera_id == test_camera_id
    assert timestamp_logger._save_directory == test_directory


def test_logging_timestamps(image_fixture: np.ndarray):
    # Arrange
    test_directory = "test_directory"
    test_camera_id = CameraId(1)
    timestamp_logger = CameraTimestampLogger(
        main_timestamps_directory=test_directory, camera_id=test_camera_id
    )
    test_frame_payload = FramePayload.create_hydrated_dummy(
        image=image_fixture
    )

    timestamp_logger.set_time_mapping(perf_counter_to_unix_mapping=(0, 0))

    # Act
    iterations = 10
    logs = []
    for i in range(iterations):
        test_frame_payload.timestamp_ns += 1
        logs.append(
            timestamp_logger.log_timestamp(multi_frame_number=i, frame=test_frame_payload)
        )

    # Assert
    df = timestamp_logger.to_dataframe()
    assert logs[-1].perf_counter_ns_timestamp == test_frame_payload.timestamp_ns
    assert len(timestamp_logger._timestamp_logs) == iterations
    assert timestamp_logger._previous_frame_timestamp == test_frame_payload.timestamp_ns
    assert df.shape[0] == 10
    assert df["perf_counter_ns_timestamp"][-1] == test_frame_payload.timestamp_ns
