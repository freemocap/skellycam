import logging
import multiprocessing
import time
from copy import deepcopy
from pathlib import Path
from time import sleep
from typing import List, Dict

import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.save_synchronized_videos import save_synchronized_videos
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder


logger = logging.getLogger(__name__)


def save_all_at_end_process(frame_lists_by_camera: Dict[str, List[FramePayload]],
                            folder_to_save_videos: List[str],
                            dump_frames_to_video_event: multiprocessing.Event,
                            ):
    logger.info("Starting VideoSaveBackgroundProcess")
    video_recorders = {}

    while True:
        sleep(1)
        # logger.debug("Video Save Process - Checking if frames need to be saved...")
        if dump_frames_to_video_event.is_set():

            logger.info("Video Save Process - There are frames to save!")

            logger.debug("Clearing dump_frames_to_video_event...")
            dump_frames_to_video_event.clear()

            for camera_id, frame_list in frame_lists_by_camera.items():
                logger.info(f"VIDEO SAVE PROCESS - {camera_id} has {len(frame_list)} frames in the list")

                video_recorders[camera_id] = VideoRecorder()

                tik = time.perf_counter()
                video_recorders[camera_id].frame_list = deepcopy(frame_list[1:])
                deepcopy_duration = time.perf_counter()- tik

                logger.debug(f" Camera {camera_id} - deepcopy_duration: {deepcopy_duration:.4f}")

                if len(video_recorders[camera_id].frame_list) == 0:
                    logger.error(f"VIDEO SAVE PROCESS - {camera_id} has no frames to save")
                    raise Exception(f"VIDEO SAVE PROCESS - {camera_id} has no frames to save")

                if np.isinf(video_recorders[camera_id].frames_per_second):
                    raise Exception(f"VIDEO SAVE PROCESS - {camera_id} frames_per_second is inf")

                logger.info(f"VideoRecorder {camera_id} - {video_recorders[camera_id].number_of_frames} frames at {video_recorders[camera_id].frames_per_second} fps")

            logger.debug(
                f"Saving frames to video files - {[video_recorder.number_of_frames for video_recorder in video_recorders.values()]}...")



            folder_to_save_videos_path = str(Path(folder_to_save_videos.pop()))

            save_synchronized_videos(
                raw_video_recorders=video_recorders,
                folder_to_save_videos=folder_to_save_videos_path,
                create_diagnostic_plots_bool=True,
            )

            logger.info(
                f"`Saved synchronized videos to folder: {folder_to_save_videos_path}")


        if not multiprocessing.parent_process().is_alive():
            logger.info("Parent process is dead. Exiting")
            break
