import logging
import multiprocessing
from typing import List, Dict

import numpy as np

from skellycam.opencv.video_recorder.video_save_background_process.save_processes.stream_save.video_saver import \
    VideoSaver

logger = logging.getLogger(__name__)


class StreamSave:
    """
    Saves frames (and timestamps) to video files as they are received.
    """

    def __init__(
            self,
            camera_ids: List[str],
            multi_frame_pipe_connection: multiprocessing.Pipe,
            stop_recording_event: multiprocessing.Event,
            save_folder_path_pipe_connection: multiprocessing.Pipe,
    ):
        self._camera_ids = camera_ids
        self._multi_frame_pipe_connection = multi_frame_pipe_connection
        self._stop_recording_event = stop_recording_event
        self._save_folder_path_pipe_connection = save_folder_path_pipe_connection

    def run(self):
        recording_in_progress = False
        unsaved_timestamps = {camera_id: [] for camera_id in self._camera_ids}
        while True:
            if self._save_folder_path_pipe_connection.poll():
                recording_in_progress = True

                video_save_paths = self._save_folder_path_pipe_connection.recv()
                logger.info(f"Saving frames to video files:\n{video_save_paths}\n")
                self._video_savers = {camera_id: VideoSaver(
                    video_file_save_path=video_save_path,
                    estimated_framerate=30,
                ) for camera_id, video_save_path in video_save_paths.items()}

            if self._multi_frame_pipe_connection.poll():
                multi_frame = self._multi_frame_pipe_connection.recv()
                for camera_id, frame in multi_frame.items():
                    unsaved_timestamps[camera_id].append(frame.timestamp_ns)

                    if recording_in_progress:
                        self._video_savers[camera_id].save_frame_to_video_file(frame=frame)

            if self._stop_recording_event.is_set() and recording_in_progress:
                logger.info("Stop recording event is set, draining remaining frames.")
                self._save_remaining_frames()

    def _save_remaining_frames(self):
        while self._multi_frame_pipe_connection.poll():
            multi_frame = self._multi_frame_pipe_connection.recv()
            for camera_id, frame in multi_frame.items():
                self._video_savers[camera_id].save_frame_to_video_file(frame=frame)

    def _estimate_framerate(self,
                            timestamps_by_camera: Dict[str, List[float]],
                            max_variability_ratio: float = .1) -> float:
        mean_fps_per_camera = []
        for timestamps in timestamps_by_camera.values():
            assert len(timestamps) > 0, "No timestamps to estimate framerate from!"
            timestamps = np.asarray(timestamps)
            timestamps = timestamps / 1e9  # convert to seconds
            frame_durations = np.diff(timestamps)
            frames_per_second = 1 / frame_durations
            mean_fps_per_camera.append(np.mean(frames_per_second))
        mean_fps = np.mean(mean_fps_per_camera)
        std_fps = np.std(mean_fps_per_camera)

        assert std_fps < mean_fps * max_variability_ratio, f"Framerate variability is greater than {max_variability_ratio * 100}% of the framerate!"
        logger.info(f"Estimated framerate: {mean_fps:.2f} +/- {std_fps:.2f} fps")

        return mean_fps
