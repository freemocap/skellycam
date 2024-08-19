import logging
from pathlib import Path

import cv2
from pydantic import BaseModel, ValidationError

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.frames.payload_models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class VideoSaver(BaseModel):
    camera_id: CameraId
    video_writer: cv2.VideoWriter

    @classmethod
    def create(cls,
               recording_name: str,
               videos_folder: str,
               frame: FramePayload,
               config: CameraConfig,
               ):
        video_file_path = str(
            Path(videos_folder) / f"{recording_name}_camera_{frame.camera_id}.{config.video_file_format}")
        writer = cls._initialize_video_writer(frame=frame,
                                              config=config,
                                              video_file_path=video_file_path)
        logger.debug(f"Created VideoSaver for camera {frame.camera_id} with video file path: {video_file_path}")
        return cls(camera_id=frame.camera_id,
                   video_writer=writer)

    def add_frame(self, frame: FramePayload):
        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (before adding frame)!")
        self.video_writer.write(frame.image)

        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (after adding frame)!")

    @classmethod
    def _initialize_video_writer(cls,
                                 frame: FramePayload,
                                 config: CameraConfig,
                                 video_file_path: str):
        writer = cv2.VideoWriter(
            video_file_path,  # full path to video file
            cv2.VideoWriter_fourcc(*config.writer_fourcc),  # fourcc
            config.framerate,  # fps
            (frame.width, frame.height),  # frameSize
        )
        if not writer.isOpened():
            raise ValidationError(f"Failed to open video writer for camera {frame.camera_id}")

        return writer
