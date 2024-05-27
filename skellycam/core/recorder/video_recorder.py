import logging
from pathlib import Path
from typing import Optional, Dict

import cv2

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class FailedToWriteFrameToVideoException(Exception):
    pass


class VideoRecorder:
    def __init__(
        self,
        camera_config: CameraConfig,
        video_save_path: str,
    ):
        self._perf_counter_to_unix_mapping: Optional[Dict[int, int]] = None
        self._camera_config = camera_config
        self._video_save_path = Path(video_save_path)

        self._previous_frame_timestamp: Optional[int] = None
        self._initialization_frame: Optional[FramePayload] = None
        self._cv2_video_writer: Optional[cv2.VideoWriter] = None
        self._timestamp_file = None

    def save_frame_to_disk(self, frame_payload: FramePayload):
        """
        Save a single frame directly to the video file on disk.
        """
        if self._initialization_frame is None:
            self._initialize_on_first_frame(frame_payload)
        self._validate_frame(frame=frame_payload)
        self._write_image_to_video_file(frame_payload)

    def _write_image_to_video_file(self, frame: FramePayload):
        self._check_if_writer_open()
        self._validate_frame(frame=frame)
        image = frame.get_image()
        self._cv2_video_writer.write(image)

    def _check_if_writer_open(self):
        if self._cv2_video_writer is None:
            raise AssertionError(
                "VideoWriter is None, but `_check_if_writer_open` was called! "
                "There's a buggo in the qt_application logic somewhere..."
            )

        if not self._cv2_video_writer.isOpened():
            if Path(self._video_save_path).exists():
                raise AssertionError(
                    f"VideoWriter is not open, but video file already exists at {self._video_save_path} - looks like the VideoWriter initialized properly but closed unexpectedly!"
                )
            else:
                raise AssertionError(
                    "VideoWriter is not open and video file doesn't exist - looks like the VideoWriter failed to initialize!"
                )

    def close(self):
        logger.debug(
            f"Closing video recorder for camera {self._camera_config.camera_id}"
        )
        self._cv2_video_writer.release() if self._cv2_video_writer is not None else None

    def _initialize_on_first_frame(self, frame_payload):
        logger.debug(
            f"Initializing video writer for camera {self._camera_config.camera_id} to save video at: {self._video_save_path} using first frame with resolution: {frame_payload.get_resolution()}"
        )
        self._initialization_frame = frame_payload.copy(deep=True)
        self._cv2_video_writer = self._create_video_writer()
        self._check_if_writer_open()
        self._previous_frame_timestamp = frame_payload.timestamp_ns

    def _create_video_writer(
        self,
    ) -> cv2.VideoWriter:
        logger.debug(
            f"Creating video writer for camera {self._camera_config.camera_id} to save video at: {self._video_save_path}"
        )
        self._video_save_path.parent.mkdir(parents=True, exist_ok=True)
        video_writer_object = cv2.VideoWriter(
            str(self._video_save_path),
            cv2.VideoWriter_fourcc(*self._camera_config.writer_fourcc),
            self._camera_config.framerate,
            self._initialization_frame.get_resolution(),
        )

        if not video_writer_object.isOpened():
            raise Exception("cv2.VideoWriter failed to initialize!")

        return video_writer_object

    def _validate_frame(self, frame: FramePayload):
        if frame.get_resolution() != self._initialization_frame.get_resolution():
            raise Exception(
                f"Frame resolution {frame.get_resolution()} does not match initialization frame resolution {self._initialization_frame.get_resolution()}"
            )
