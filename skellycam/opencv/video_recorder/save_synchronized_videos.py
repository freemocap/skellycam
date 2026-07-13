import logging
import platform
from pathlib import Path
from typing import Dict, Union

from skellycam.opencv.video_recorder.streaming_video_writer import StreamingWriterResult
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


def save_synchronized_videos(
        dictionary_of_video_recorders: Dict[str, VideoRecorder],
        folder_to_save_videos: Union[str, Path],
        create_diagnostic_plots_bool: bool = True,
        stop_timeout_seconds: float = 10.0,
) -> Dict[str, StreamingWriterResult]:
    """Finalizes an already-streamed synchronized recording.

    Historically this function held every camera's full raw-frame list in
    RAM simultaneously, clipped/matched them by nearest timestamp, and only
    then wrote anything to disk -- the root cause this rewrite exists to fix
    (see ARCHITECTURE_REPORT.md). Frames are now written to disk during
    capture by each camera's own StreamingVideoWriter (bounded queue, opened
    at recording Start -- see video_recorder.py / camera_group_thread_worker.py).
    Cross-camera synchronization now happens per-frame at capture time
    (camera_group_thread_worker._try_record_synchronized_frame_bundle):
    every enabled camera either writes the same global frame_index, or the
    whole recording is aborted -- so by the time this function runs, frame
    counts across cameras should already match by construction.

    This function's only remaining job is to drain each camera's writer,
    validate that every camera actually finished cleanly with matching frame
    counts, and report an honest result. It never holds frame image data.
    """
    logger.info(f"Finalizing synchronized recording in folder: {str(folder_to_save_videos)}")

    results: Dict[str, StreamingWriterResult] = {}
    for camera_id, video_recorder in dictionary_of_video_recorders.items():
        results[camera_id] = video_recorder.stop_streaming(timeout_seconds=stop_timeout_seconds)

    frame_counts = {camera_id: result.frames_written for camera_id, result in results.items()}
    logger.info(f"Frames written per camera: {frame_counts}")

    all_succeeded = all(result.success for result in results.values())
    distinct_counts = set(frame_counts.values())
    counts_match = len(distinct_counts) <= 1

    if not all_succeeded or not counts_match:
        failed_cameras = [camera_id for camera_id, result in results.items() if not result.success]
        logger.error(
            "Synchronized recording did NOT finalize cleanly -- "
            f"all_succeeded={all_succeeded} counts_match={counts_match} "
            f"frame_counts={frame_counts} failed_cameras={failed_cameras}. "
            "Partial/.failure.json files are preserved on disk for inspection; "
            "no camera's output was marked complete/renamed unless it "
            "individually succeeded."
        )
        return results

    logger.info(f"Synchronized recording finalized successfully: {frame_counts}")

    if platform.system() == "Windows" and create_diagnostic_plots_bool:
        logger.warning(
            "Diagnostic plots are not available with the streaming recorder "
            "(they required the previous full in-RAM frame buffer, which no "
            "longer exists by design). Skipped -- see "
            "docs/STREAMING_RECORDING_FAILURE_RECOVERY.md."
        )

    return results
