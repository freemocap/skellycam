import logging
import traceback
from pathlib import Path
from typing import Union

import cv2
import numpy as np

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.video_save_background_process.save_processes.stream_save.timestamp_manager import \
    TimestampManager

logger = logging.getLogger(__name__)


class VideoSaver:

    def __init__(self,
                 video_file_save_path: Union[str, Path],
                 ):

        self._estimated_framerate = None
        self._video_file_save_path = video_file_save_path

        self._frames_to_save = []
        self._initialization_frames = []
        self._initialized_framerate = None
        self._initialize_file_path()

        self._video_writer = None

        self._timestamp_manager = self._create_timestamp_manager()

    def _create_timestamp_manager(self):
        timestamp_file_name = self._video_file_save_path.stem + "_timestamps.csv"
        return TimestampManager(timestamp_file_save_path=self._video_file_save_path.parent / timestamp_file_name)

    def _initialize_file_path(self):
        try:
            self._video_file_save_path = Path(self._video_file_save_path)
            self._video_file_save_path.parent.mkdir(parents=True, exist_ok=True)
            self._video_file_save_path.touch(exist_ok=True)
        except Exception as e:
            logger.error(f"Error initializing video file path: {e}")
            logger.error(traceback.format_exc())

    def save_frame_to_video_file(self, frame=FramePayload):
        if self._video_writer is None:
            self._video_writer = self._initialize_video_writer(example_image=frame.image,
                                                               fourcc="mp4v")

        assert self._video_writer is not None, "Video writer is not initialized"
        assert self._video_writer.isOpened(), "Video writer is not opened"
        self._video_writer.write(frame.image)

        self._timestamp_manager.receive_new_timestamp(timestamp_ns=frame.timestamp_ns)

    def _initialize_video_writer(
            self,
            example_image: np.ndarray,

            fourcc: str = "mp4v",
    ) -> cv2.VideoWriter:

        image_height, image_width, _ = example_image.shape
        video_writer_object = cv2.VideoWriter(
            str(self._video_file_save_path),
            cv2.VideoWriter_fourcc(*fourcc),
            self._estimate_framerate(),
            (int(image_width), int(image_height)),
        )
        if not video_writer_object.isOpened():
            logger.error(
                f"cv2.VideoWriter failed to initialize for: {str(self._video_file_save_path)}"
            )
            raise Exception(f"cv2.VideoWriter failed to initialize for: {str(self._video_file_save_path)}")
        return video_writer_object

    def close(self):
        self._video_writer.release()
        self._timestamp_manager.close()

    def _estimate_framerate(self):
        self._timestamp_manager.estimate_framerate()
