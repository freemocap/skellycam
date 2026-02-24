import numpy as np

from skellycam.core.timestamps.numpy_timestamps.calculate_timestamps_numpy import calculate_durations
from skellycam.core.types.numpy_record_dtypes import FRAME_LIFECYCLE_TIMESTAMPS_DTYPE, TimestampsArray, DurationArray
from skellycam.core.types.type_overloads import CameraIdString


async def process_recording_timestamps(
        frame_metadatas_by_camera: dict[CameraIdString, list[np.recarray]],
        frame_numbers: list[int]
) -> tuple[TimestampsArray, DurationArray]:

    # Get dimensions
    camera_ids = list(frame_metadatas_by_camera.keys())
    num_cameras = len(camera_ids)
    num_frames = len(frame_numbers)

    # Create combined array for all cameras
    all_timestamps = np.recarray((num_cameras, num_frames), dtype=FRAME_LIFECYCLE_TIMESTAMPS_DTYPE)

    # Fill the array with data from each camera on each frame
    for frame_number in range(num_frames):
        for camera_index, camera_id in enumerate(camera_ids):
            all_timestamps[camera_index, frame_number] = frame_metadatas_by_camera[camera_id][frame_number].timestamps[0]

    # Calculate durations
    all_durations = await calculate_durations(all_timestamps=all_timestamps)

    # # Calculate statistics
    # timestamp_statistics = calculate_frame_timestamps_statistics(all_timestamps=all_timestamps,
    #                                                              all_durations=all_durations)

    return all_timestamps, all_durations
