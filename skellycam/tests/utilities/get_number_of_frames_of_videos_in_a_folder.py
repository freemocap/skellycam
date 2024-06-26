import logging
from pathlib import Path
from typing import Union

import cv2

logger = logging.getLogger(__name__)


def get_number_of_frames_of_videos_in_a_folder(folder_path: Union[str, Path]):
    """
    Get the number of frames in the first video in a folder
    """

    list_of_video_paths = list(Path(folder_path).glob("*.mp4"))

    if len(list_of_video_paths) == 0:
        logger.error(f"No videos found in {folder_path}")
        return None

    frame_count = []

    for video_path in list_of_video_paths:
        cap = cv2.VideoCapture(str(video_path))
        # Note: cap.get(cv2.CAP_PROP_FRAME_COUNT) may not always be accurate - https://stackoverflow.com/a/47796468/14662833
        success = True
        count = 0
        while success:
            success, frame = cap.read()
            if not success:
                break
            count += 1
        cap.release()
        frame_count.append(count)

    logger.info(f"Number of frames is - {frame_count} - for videos in {folder_path}")
    return frame_count
