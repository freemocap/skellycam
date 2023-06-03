import logging
import multiprocessing
from copy import deepcopy
from pathlib import Path
from time import sleep
from typing import List, Dict

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.save_synchronized_videos import (
    save_synchronized_videos,
)
from skellycam.opencv.video_recorder.video_save_background_process.save_processes.stream_save.video_saver import \
    VideoSaver

logger = logging.getLogger(__name__)


class StreamSave:
    """
    Saves frames (and timestamps) to video files as they are received.
    """

    def __init__(
            self,
            frame_databases_by_camera_id: Dict[str, Dict[multiprocessing.Value, List[FramePayload]]],

    ):

        self._frame_databases_by_camera_id = frame_databases_by_camera_id

    def run(self,
            video_file_paths: Dict[str, str],
            stop_recording_event: multiprocessing.Event,
            ):
        logger.info(f"Saving frames to video files:\n{video_file_paths}\n")

        assert all([camera_id in video_file_paths.keys() for camera_id in self._frame_databases_by_camera_id.keys()]),\
            "Mis-match between camera IDs and video file paths!"

        self._video_savers = {camera_id: VideoSaver(
            video_file_save_path=video_save_path,
        ) for camera_id, video_save_path in video_file_paths.items()}

        self._save_frame_index = -1
        while True:
            for camera_id, frame_database in self._frame_databases_by_camera_id.items():
                self._save_frame_index +=1
                if self._save_frame_index >= len(frame_database["frames"]):
                    self._save_frame_index = 0

                shared_memory_frame = frame_database["frames"][self._save_frame_index]
                shared_memory_frame.accessed = True
                frame_to_save = deepcopy(shared_memory_frame)
                self._video_savers[camera_id].save_frame_to_video_file(frame=frame_to_save)

            if stop_recording_event.is_set():
                logger.info("Stop recording event is set, draining remaining frames.")
                self._save_remaining_frames()

    def _save_remaining_frames(self):
        for camera_id, frame_database in self._frame_databases_by_camera_id.items():
            while True:
                shared_memory_frame = frame_database["frames"][self._save_frame_index]

                if shared_memory_frame.accessed:
                    break

                shared_memory_frame.accessed = True

                frame_to_save = deepcopy(shared_memory_frame)
                self._video_savers[camera_id].save_frame_to_video_file(frame=frame_to_save)

