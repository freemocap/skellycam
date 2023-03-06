import logging
import multiprocessing
import time
from copy import deepcopy
from pathlib import Path
from typing import List, Dict

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam.opencv.video_recorder.save_synchronized_videos import (
    save_synchronized_videos,
)
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


class SaveAll:
    def __init__(
        self,
        frame_lists_by_camera: Dict[str, List[FramePayload]],
        folder_to_save_videos: List[str],
        dump_frames_to_video_event: multiprocessing.Event,
    ):
        self._frame_lists_by_camera = frame_lists_by_camera
        self._folder_to_save_videos = folder_to_save_videos
        self._dump_frames_to_video_event = dump_frames_to_video_event
        self._video_recorders: Dict[CameraId, VideoRecorder] = {}

    def run(self):
        # logger.debug("Video Save Process - Checking if frames need to be saved...")
        if self._dump_frames_to_video_event.is_set():
            logger.info("Video Save Process - There are frames to save!")

            logger.debug("Clearing dump_frames_to_video_event...")
            self._dump_frames_to_video_event.clear()

            for camera_id, frame_list in self._frame_lists_by_camera.items():
                logger.info(
                    f"VIDEO SAVE PROCESS - {camera_id} has {len(frame_list)} frames in the list"
                )

                self._video_recorders[camera_id] = VideoRecorder()

                tik = time.perf_counter()
                self._video_recorders[camera_id].frame_list = deepcopy(frame_list[1:])
                deepcopy_duration = time.perf_counter() - tik

                logger.debug(
                    f" Camera {camera_id} - deepcopy_duration: {deepcopy_duration:.4f}"
                )

                if len(self._video_recorders[camera_id].frame_list) == 0:
                    logger.error(
                        f"VIDEO SAVE PROCESS - {camera_id} has no frames to save"
                    )
                    raise Exception(
                        f"VIDEO SAVE PROCESS - {camera_id} has no frames to save"
                    )

                if np.isinf(self._video_recorders[camera_id].frames_per_second):
                    raise Exception(
                        f"VIDEO SAVE PROCESS - {camera_id} frames_per_second is inf"
                    )

                logger.info(
                    f"VideoRecorder {camera_id} - "
                    f"{self._video_recorders[camera_id].number_of_frames} "
                    f"frames at {self._video_recorders[camera_id].frames_per_second} fps"
                )

            logger.debug(
                f"Saving frames to video files - "
                f"{[video_recorder.number_of_frames for video_recorder in self._video_recorders.values()]}..."
            )

            folder_to_save_videos_path = str(Path(self._folder_to_save_videos.pop()))

            save_synchronized_videos(
                raw_video_recorders=self._video_recorders,
                folder_to_save_videos=folder_to_save_videos_path,
                create_diagnostic_plots_bool=True,
            )

            logger.info(
                f"`Saved synchronized videos to folder: {folder_to_save_videos_path}"
            )
