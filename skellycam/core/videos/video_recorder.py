import logging
from pathlib import Path
from typing import List

import cv2
from pydantic import BaseModel, ValidationError

from skellycam.core import CameraId
from skellycam.core.cameras.camera.config.camera_config import CameraConfig
from skellycam.core.frames.payloads.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class VideoRecorder(BaseModel):
    camera_id: CameraId
    video_path: str
    video_writer: cv2.VideoWriter
    camera_config: CameraConfig
    _frames_to_write: List[FramePayload] = []

    class Config:
        arbitrary_types_allowed = True

    @property
    def number_of_frames_to_write(self) -> int:
        return len(self._frames_to_write)

    @classmethod
    def create(cls,
               recording_name: str,
               videos_folder: str,
               config: CameraConfig,
               ):
        Path(videos_folder).mkdir(parents=True, exist_ok=True)
        video_file_path = str(
            Path(videos_folder) / f"{recording_name}_camera_{config.camera_id}{config.video_file_extension}")
        writer = cls._initialize_video_writer(config=config,
                                              video_file_path=video_file_path)
        logger.debug(f"Created VideoSaver for camera {config.camera_id} with video file path: {video_file_path}")
        return cls(camera_id=config.camera_id,
                   video_path=video_file_path,
                   video_writer=writer,
                   camera_config=config,
                   )

    def add_frame(self, frame: FramePayload):
        self._frames_to_write.append(frame)

    def write_one_frame(self):
        if len(self._frames_to_write) == 0:
            return

        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (before adding frame)!")

        frame = self._frames_to_write.pop(0)
        self._validate_frame(frame)
        self.video_writer.write(frame.image)
        logger.loop(f"Added frame# {frame.frame_number} to VideoSaver for camera {self.camera_id}")

        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (after adding frame)!")

    def finish_and_close(self):
        logger.debug(f"Finishing and closing VideoSaver for camera {self.camera_id}")
        while len(self._frames_to_write) > 0:
            self.write_one_frame()
        self.close()

    @classmethod
    def _initialize_video_writer(cls,
                                 config: CameraConfig,
                                 video_file_path: str):
        writer = cv2.VideoWriter(
            video_file_path,  # full path to video file
            cv2.VideoWriter_fourcc(*config.writer_fourcc),  # fourcc
            config.framerate,  # fps
            (config.resolution.width, config.resolution.height),  # frameSize
        )
        if not writer.isOpened():
            raise ValidationError(f"Failed to open video writer for camera {config.camera_id}")
        logger.debug(
            f"Initialized VideoWriter for camera {config.camera_id} - Video file will be saved to {video_file_path}")
        return writer

    def _validate_frame(self, frame: FramePayload):
        if not Path(self.video_path).parent.exists():
            Path(self.video_path).parent.mkdir(parents=True, exist_ok=True)
        if frame.camera_id != self.camera_config.camera_id:
            raise ValidationError(
                f"Frame camera_id {frame.camera_id} does not match self.camera_config camera_id {self.camera_config.camera_id}")
        if frame.image.shape != (
        self.camera_config.resolution.height, self.camera_config.resolution.width, self.camera_config.color_channels):
            raise ValidationError(f"Frame shape {frame.image.shape} does not match self.camera_config shape "
                                  f"({self.camera_config.resolution.height}, {self.camera_config.resolution.width}, {self.camera_config.color_channels})")

    def _clean_up_empty_video_file(self, min_size_bytes=10_000):
        if Path(self.video_path).exists() and Path(self.video_path).stat().st_size < min_size_bytes:
            Path(self.video_path).unlink()
            logger.trace(f"Deleted empty video file at {self.video_path}")
    def close(self):
        self.video_writer.release()
        self._clean_up_empty_video_file()
        logger.debug(f"Closed VideoSaver for camera {self.camera_id} - Video file saved to {self.video_path}")
