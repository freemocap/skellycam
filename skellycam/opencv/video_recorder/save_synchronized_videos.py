import logging
from pathlib import Path
from typing import Dict, Union, List, Tuple

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.diagnostics.create_diagnostic_plots import create_diagnostic_plots
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.tests.test_frame_counts_equal import test_frame_counts_equal
from skellycam.tests.test_synchronized_video_frame_counts import test_synchronized_video_frame_counts
from skellycam.utilities.is_monotonic import is_monotonic

logger = logging.getLogger(__name__)


def save_synchronized_videos(
        raw_video_recorders: Dict[str, VideoRecorder],
        folder_to_save_videos: Union[str, Path],
        create_diagnostic_plots_bool: bool = True,
):
    logger.info(f"Saving synchronized videos to folder: {str(folder_to_save_videos)}")

    raw_timestamps = {camera_id: video_recorder.timestamps for camera_id, video_recorder in raw_video_recorders.items()}
    clipped_frame_lists, latest_first_frame, earliest_final_frame, mean_frame_duration_ns = clip_frame_lists(
        raw_video_recorders)
    reference_timestamps_ns = list(np.arange(latest_first_frame, earliest_final_frame, mean_frame_duration_ns))
    if not is_monotonic(reference_timestamps_ns):
        raise Exception("reference_timestamps_ns is not monotonic")
    logger.info(
        f"reference number of frames: {len(reference_timestamps_ns)},"
        f" raw/clipped video number of frames: {[len(l) for l in clipped_frame_lists.values()]}")

    synchronized_video_recorders = initialize_synchronized_video_recorders(folder_to_save_videos=folder_to_save_videos,
                                                                           frame_lists=clipped_frame_lists,
                                                                           reference_first_timestamp_ns=reference_timestamps_ns.pop(
                                                                               0),
                                                                           frame_duration_ns=mean_frame_duration_ns)

    inter_camera_timestamp_differences = {camera_id: [] for camera_id in raw_video_recorders.keys()}
    for reference_frame_number, reference_frame_timestamp in enumerate(reference_timestamps_ns):

        for camera_id, synchronized_video_recorder in synchronized_video_recorders.items():

            frame_timestamp_difference = reference_frame_timestamp - raw_video_recorders[camera_id].frame_list[
                0].timestamp_ns
            inter_camera_timestamp_differences[camera_id].append(frame_timestamp_difference)
            if abs(frame_timestamp_difference) < mean_frame_duration_ns:
                synchronized_video_recorders[camera_id].append_frame_payload_to_list(
                    raw_video_recorders[camera_id].frame_list.pop(0))
            else:
                synchronized_video_recorders[camera_id].append_frame_payload_to_list(
                    synchronized_video_recorders[camera_id].frame_list[-1]
                )

    test_frame_counts_equal(frame_lists={camera_id: v.frame_list for camera_id, v in
                                         synchronized_video_recorders.items()})

    # plot_inter_camera_timestamp_differences(inter_camera_timestamp_differences)

    Path(folder_to_save_videos).mkdir(parents=True, exist_ok=True)

    if create_diagnostic_plots_bool:
        create_diagnostic_plots(
            raw_timestamps=raw_timestamps,
            synchronized_video_recorders=synchronized_video_recorders,
            inter_camera_timestamp_differences=inter_camera_timestamp_differences,
            folder_to_save_plots=folder_to_save_videos,
            show_plots_bool=True,
        )

    for camera_id, synchronized_video_recorder in synchronized_video_recorders.items():

        if synchronized_video_recorder.number_of_frames > 0:
            logger.info(
                f" Saving camera {camera_id} video with {synchronized_video_recorder.number_of_frames} frames..."
            )
            synchronized_video_recorder.save_frame_list_to_video_file()
        else:
            raise Exception(f"Camera {camera_id} has no frames to save!")

    test_synchronized_video_frame_counts(video_folder_path=folder_to_save_videos)
    logger.info(f"Done!")


def plot_inter_camera_timestamp_differences(inter_camera_timestamp_differences: Dict[str, List[float]]):
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('QtAgg')
    figure, axes = plt.subplots(1, 1, figsize=(10, 10))
    figure.suptitle("Inter-camera timestamp differences")
    axes.xaxis.set_label_text("Frame number")
    axes.yaxis.set_label_text("Timestamp difference (sec)")
    for camera_id, timestamp_differences in inter_camera_timestamp_differences.items():
        axes.plot(np.asarray(timestamp_differences) / 1e9, '.', label=camera_id)
    axes.legend()
    plt.show()


def clip_frame_lists(raw_video_recorders: Dict[str, VideoRecorder]) -> Tuple[Dict[str, List[FramePayload]],
float,
float,
float]:
    test_recorder_validity(raw_video_recorders)

    first_frame_timestamps = np.asarray([v.frame_list[0].timestamp_ns for v in raw_video_recorders.values()])
    final_frame_timestamps = np.asarray([v.frame_list[-1].timestamp_ns for v in raw_video_recorders.values()])

    latest_first_frame = np.max(first_frame_timestamps)
    earliest_final_frame = np.min(final_frame_timestamps)

    frame_duration_ns_per_camera = np.asarray([video_recorders.median_frame_duration_ns for video_recorders in
                                               raw_video_recorders.values()])
    mean_frame_duration_ns = np.mean(frame_duration_ns_per_camera)

    if not latest_first_frame < earliest_final_frame:
        raise Exception("The `latest_first_frame` is not before the `earliest_final_frame`!")

    logger.info(f"first_frame_timestamps: {str(first_frame_timestamps / 1e9)} seconds")
    logger.info(f"np.diff(first_frame_timestamps): {str(np.diff(first_frame_timestamps) / 1e9)} seconds")
    logger.info(f"latest_first_frame: {str(latest_first_frame / 1e9)} seconds")
    logger.info(f"final_frame_timestamps: {str(final_frame_timestamps / 1e9)} seconds")
    logger.info(f"np.diff(final_frame_timestamps): {str(np.diff(final_frame_timestamps) / 1e9)} seconds")
    logger.info(f"earliest_final_frame: {str(earliest_final_frame / 1e9)} seconds")
    logger.info(f"Recording duration: {str((earliest_final_frame - latest_first_frame) / 1e9)} seconds")
    logger.info(
        f"frame_duration_ns_per_camera: {frame_duration_ns_per_camera / 1e9}, mean:{mean_frame_duration_ns / 1e9} seconds per frame")

    clipped_frame_lists = {}
    for camera_id, raw_video_recorder in raw_video_recorders.items():
        logger.info(f"Camera {camera_id} has {raw_video_recorder.number_of_frames} frames")
        clipped_frame_list = raw_video_recorder.frame_list
        off_the_front = 0
        off_the_back = 0
        while clipped_frame_list[0].timestamp_ns <= latest_first_frame - mean_frame_duration_ns:
            off_the_front += 1
            clipped_frame_list.pop(0)
        while clipped_frame_list[-1].timestamp_ns >= earliest_final_frame + mean_frame_duration_ns:
            off_the_back += 1
            clipped_frame_list.pop(-1)

        logger.info(
            f"Camera {camera_id} has {len(clipped_frame_list)} frames after clipping {off_the_front} from the front and {off_the_back} from the back")
        clipped_frame_lists[camera_id] = clipped_frame_list

    return clipped_frame_lists, float(latest_first_frame), float(earliest_final_frame), float(mean_frame_duration_ns)


def initialize_synchronized_video_recorders(folder_to_save_videos: Union[str, Path],
                                            frame_lists: Dict[str, List[FramePayload]],
                                            reference_first_timestamp_ns: Union[int, float],
                                            frame_duration_ns: Union[int, float]):
    initial_frame_differences = {camera_id: (l[0].timestamp_ns - reference_first_timestamp_ns) / 1e9 for
                                 camera_id, l in frame_lists.items()}

    logger.info(f"Initialized synchronized video recorders - first frame time difference from reference: "
                f"{initial_frame_differences}")

    synchronized_video_recorders = {}
    for camera_id, frame_list in frame_lists.items():

        synchronized_video_path = Path(folder_to_save_videos) / f"Camera_{str(camera_id).zfill(3)}_synchronized.mp4"
        synchronized_video_recorders[camera_id] = VideoRecorder(video_file_save_path=synchronized_video_path)
        synchronized_video_recorders[camera_id].append_frame_payload_to_list(frame_list.pop(0))

        difference_from_reference = reference_first_timestamp_ns - \
                                    synchronized_video_recorders[camera_id].timestamps[0]

        logger.info(f"Creating synchronized frame list for camera {camera_id} (raw frame count: {len(frame_list)})"
                    f" - first frame difference from reference: {difference_from_reference / 1e9:.3f} seconds")

        if np.abs(difference_from_reference) > 3 * frame_duration_ns:
            raise ValueError(
                f"Reference first timestamp {reference_first_timestamp_ns / 1e9:.3f} "
                f"is not within 3* frame_duration ({frame_duration_ns:.3f}) of "
                f"synchronized video recorder {synchronized_video_recorders[camera_id].timestamps[0] / 1e9:.3f}"
                f" (difference: ({np.abs(difference_from_reference) / 1e9:.3f})")

    return synchronized_video_recorders


def test_recorder_validity(raw_video_recorders):
    for camera_id, video_recorder in raw_video_recorders.items():

        if len(video_recorder.frame_list) == 0:
            logger.error(
                f"Camera {camera_id} has no frames to save"
            )
            raise Exception(
                f"Camera {camera_id} has no frames to save"
            )

        if np.isinf(video_recorder.frames_per_second):
            raise Exception(
                f"Camera {camera_id} frames_per_second is inf"
            )
        if not is_monotonic(video_recorder.timestamps):
            raise Exception(f"Camera {camera_id} timestamps are not monotonic!")
