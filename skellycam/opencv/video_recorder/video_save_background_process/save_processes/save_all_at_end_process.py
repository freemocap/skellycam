import logging
import multiprocessing
from copy import deepcopy
from pathlib import Path
from time import sleep
from typing import List, Dict

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.save_synchronized_videos import save_synchronized_videos
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder


logger = logging.getLogger(__name__)


def save_all_at_end_process(frame_lists_by_camera: Dict[str, List[FramePayload]],
                            video_save_paths_by_camera: Dict[str, str],
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
                frame_list_length = len(frame_list)
                logger.info(f"VIDEO SAVE PROCESS - {camera_id} has {frame_list_length} frames in the list")

                frames_to_save = deepcopy(frame_list[1:-1])
                del frame_list[1:-1]

                if not frames_to_save:
                    logger.error(f"VIDEO SAVE PROCESS - {camera_id} has no frames to save")
                    raise Exception(f"VIDEO SAVE PROCESS - {camera_id} has no frames to save")

                video_recorders[camera_id] = VideoRecorder()
                video_recorders[camera_id].frame_list = frames_to_save

            logger.debug(
                f"Saving frames to video files - {[video_recorder.number_of_frames for video_recorder in video_recorders.values()]}...")

            folder_to_save_videos = str(Path(video_save_paths_by_camera['0']).parent)

            save_synchronized_videos(
                raw_video_recorders=video_recorders,
                folder_to_save_videos=folder_to_save_videos,
                create_diagnostic_plots_bool=True,
            )

            logger.info(
                f"`Saved synchronized videos to folder: {str(folder_to_save_videos)}")


        if not multiprocessing.parent_process().is_alive():
            logger.info("Parent process is dead. Exiting")
            break
