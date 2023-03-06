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
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

FRAMES_TO_SAVE_PER_CHUNK = 100
NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE = (
    FRAMES_TO_SAVE_PER_CHUNK * 1.2
)  # how large the list
# must be before we start saving

logger = logging.getLogger(__name__)


class ChunkSave:
    _video_recorders = {}

    def __init__(
        self,
        frame_lists_by_camera: Dict[str, List[FramePayload]],
        video_save_paths: Dict[str, str],
        currently_recording_frames: multiprocessing.Value,
        save_all_at_the_end: bool = False,
    ):
        self._frame_lists_by_camera = frame_lists_by_camera
        self._video_save_paths = video_save_paths
        self._currently_recording_frames = currently_recording_frames
        self._save_all_at_the_end = save_all_at_the_end

    def run(self):
        final_chunk = False
        for camera_id, frame_list in self._frame_lists_by_camera.items():
            frame_list_length = len(frame_list)
            print(
                f"VIDEO SAVE PROCESS - {camera_id} has {frame_list_length} frames in the list"
            )

            frame_chunk = self._get_frame_chunk(frame_list)

            # This logic isn't ideal. i stopped the refactor here.
            # We need to know when recording has been stopped, not when we're no longer recording.
            # These are 2 different events that allows us to do more specific, less vague save logic.
            if not self._currently_recording_frames.value and frame_list_length > 1:
                logger.debug(
                    f"Grabbing {len(frame_list)} frames from Camera {camera_id} to save to video "
                    f"files"
                )
                frame_chunk = deepcopy(frame_list)
                del frame_list[:]
                final_chunk = True
                if self._save_all_at_the_end:
                    self._video_recorders[camera_id] = VideoRecorder(
                        video_file_save_path=self._video_save_paths[camera_id]
                    )
                    self._video_recorders[camera_id].frame_list = frame_chunk

            if frame_chunk:
                if not self._save_all_at_the_end:
                    video_file_save_path = self._video_save_paths[camera_id]

                    if video_file_save_path not in self._video_recorders:
                        logger.debug(
                            f"Creating VideoRecorder for {video_file_save_path}"
                        )
                        self._video_recorders[video_file_save_path] = VideoRecorder(
                            video_file_save_path=video_file_save_path
                        )

                    logger.debug(f"Saving {frame_list_length} frames to video files")
                    self._video_recorders[
                        video_file_save_path
                    ].save_frame_chunk_to_video_file(
                        frame_chunk, final_chunk=final_chunk
                    )

        if final_chunk:
            self._complete_final_chunk_save()

    def _get_frame_chunk(self, frames: List[FramePayload]):
        frame_list_length = len(frames)
        if self._save_all_at_the_end:
            return
        if frame_list_length < NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE:
            return
        frame_chunk = deepcopy(frames[:FRAMES_TO_SAVE_PER_CHUNK])
        # If we delete this early, we might have an issue.
        del frames[:FRAMES_TO_SAVE_PER_CHUNK]
        return frame_chunk

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
