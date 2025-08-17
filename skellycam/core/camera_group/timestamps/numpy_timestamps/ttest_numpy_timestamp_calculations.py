import time
from pathlib import Path

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.timestamps.numpy_timestamps.process_and_save_recording_timestamps import \
    process_and_save_recording_timestamps
from skellycam.core.camera_group.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE
from skellycam.core.types.numpy_record_dtypes import FRAME_METADATA_DTYPE


def ttest_numpy_timestamp_processing(num_cameras=3,
                                     num_frames=1000):
    """
    Simple test function to verify the functionality of the numpy timestamp processing.
    """

    (camera_configs,
     metadatas_by_camera,
     num_cameras,
     num_frames,
     recording_info) = create_dummy_frame_metadata(num_cameras=num_cameras,
                                                   num_frames=num_frames)

    # Process and save timestamps
    print(f"Processing {num_cameras} cameras with {num_frames} frames each...")
    start_time = time.time()

    process_and_save_recording_timestamps(
        frame_metadatas_by_camera=metadatas_by_camera,
        recording_info=recording_info,
        camera_configs=camera_configs,
    )

    end_time = time.time()
    print(f"Processing completed in {end_time - start_time:.3f} seconds")

    # Verify output files exist
    assert Path(recording_info.timestamp_file_path).exists(), "Multiframe timestamps file not created"
    assert Path(recording_info.timestamp_stats_json_file_path).exists(), "Statistics JSON file not created"
    assert Path(recording_info.timestamp_stats_text_file_path).exists(), "Statistics text file not created"

    for camera_id in camera_configs.keys():
        camera_file = Path(recording_info.camera_timestamps_file_path_from_camera_id(camera_id))
        assert camera_file.exists(), f"Camera {camera_id} timestamps file not created"

    # Clean up
    # temp_dir.cleanup()
    print("All tests passed!")


def create_dummy_frame_metadata(num_cameras:int,
                                num_frames:int):
    # Create synthetic test data

    camera_ids = [f"camera_{i}" for i in range(num_cameras)]
    # Create a temporary directory for test output
    recording_path = Path(__file__).parent / "test_timestamps_recording"
    recording_path.mkdir(exist_ok=True)
    # Create RecordingInfo
    recording_info = RecordingInfo(recording_directory=str(recording_path),
                                   recording_name="test_recording1")
    # Generate synthetic timestamps

    timebase_mapping = TimebaseMapping().to_numpy_record_array()
    base_time = time.perf_counter_ns()
    configs = {}
    metadatas_by_camera = {}
    camera_index = 0

    def get_jitter() -> int:
        """Generate a random jitter value between -1000 and 1000 nanoseconds."""
        return np.random.randint(0, 1_000)

    for camera_id in camera_ids:
        metadatas_by_camera[camera_id] = []
        configs[camera_id] = CameraConfig(camera_id=camera_id, camera_index=camera_index)
        camera_index += 1
    for fr in range(num_frames):
        for camera_id in camera_ids:
            # timestamps = np.zeros(num_frames, dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)
            metadata = np.recarray(1, dtype=FRAME_METADATA_DTYPE)
            timestamps = np.recarray(1, dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

            frame_time = base_time + fr * 33_333_333 + get_jitter()  # 30 FPS base time with jitter

            # Create timebase mapping
            metadata.timebase_mapping[0] = timebase_mapping

            # Fill timestamp fields with realistic values
            timestamps.frame_initialized_ns = frame_time + get_jitter() - 500_000
            timestamps.pre_frame_grab_ns = frame_time + get_jitter()
            timestamps.post_frame_grab_ns = frame_time + get_jitter() + 2_000_000
            timestamps.pre_frame_retrieve_ns = frame_time + get_jitter() + 3_000_000
            timestamps.post_frame_retrieve_ns = frame_time + get_jitter() + 5_000_000
            timestamps.pre_copy_to_camera_shm_ns = frame_time + get_jitter() + 6_000_000
            timestamps.post_copy_to_camera_shm_ns = frame_time + get_jitter() + 7_000_000
            timestamps.pre_frame_record_ns = frame_time + get_jitter() + 8_000_000
            timestamps.post_frame_record_ns = frame_time + get_jitter() + 10_000_000

            metadata.camera_config = configs[camera_id].to_numpy_record_array()
            metadata.timestamps = timestamps
            metadata.frame_number = fr + 100  # Start at 100 to test non-zero start
            metadatas_by_camera[camera_id].append(metadata)
    return configs, metadatas_by_camera, num_cameras, num_frames, recording_info


if __name__ == "__main__":
    ttest_numpy_timestamp_processing()
