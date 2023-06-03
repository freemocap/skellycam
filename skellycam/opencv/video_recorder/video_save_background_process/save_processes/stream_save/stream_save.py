import logging
import multiprocessing
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
            frame_lists_by_camera: Dict[str, List[FramePayload]],

    ):
        self._frame_lists_by_camera = frame_lists_by_camera

    def run(self,
            video_file_paths: Dict[str, str],
            stop_recording_event: multiprocessing.Event,
            ):
        logger.info(f"Saving frames to video files:\n{video_file_paths}\n")

        assert all([camera_id in video_file_paths.keys() for camera_id in self._frame_lists_by_camera.keys()]),\
            "Mis-match between camera IDs and video file paths!"

        video_savers = {camera_id: VideoSaver(
            video_file_save_path=video_save_path,
        ) for camera_id, video_save_path in video_file_paths.items()}

        last_run = False
        while True:
            for camera_id, frame_list in self._frame_lists_by_camera.items():
                frame_chunk = self._get_frame_chunk(frame_list)
                if len(frame_chunk) > 0:
                    for frame in frame_chunk:
                        video_savers[camera_id].save_frame_to_video_file(frame=frame)

            if stop_recording_event.is_set():
                if not last_run:
                    sleep(1)  # give it a sec then do another run to make sure we got everything
                    last_run = True
                else:
                    break

    def _get_frame_chunk(self, frames: List[FramePayload]):
        frames_to_save = []
        while len(frames) > 0:
            frame = frames.pop(0)
            frames_to_save.append(frame)
        return frames_to_save

    def _complete_final_chunk_save(self):
        logger.debug(
            f"Saving frames to video files - "
            f"{[video_recorder.number_of_frames for video_recorder in self._video_recorders.values()]}..."
        )
        synchronized_videos_folder = Path(
            self._video_save_paths["0"]
        ).parent  # hacky ugly shoe-horn to reimplement old save method

        save_synchronized_videos(
            raw_video_recorders=self._video_recorders,
            folder_to_save_videos=synchronized_videos_folder,
            create_diagnostic_plots_bool=True,
        )

        logger.info(
            f"`Saved synchronized videos to folder: {str(synchronized_videos_folder)}"
        )
