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
               frame: FramePayload,
               config: CameraConfig,
               ):
        """
        NOTE - Does not add `first frame` to video - call `add frame` after creation
        """
        video_file_path = str(
            Path(videos_folder) / f"{recording_name}_camera_{frame.camera_id}{config.video_file_extension}")
        writer = cls._initialize_video_writer(frame=frame,
                                              config=config,
                                              video_file_path=video_file_path)
        logger.debug(f"Created VideoSaver for camera {frame.camera_id} with video file path: {video_file_path}")
        return cls(camera_id=frame.camera_id,
                   video_path=video_file_path,
                   video_writer=writer)

    def add_frame(self, frame: FramePayload):
        self._frames_to_write.append(frame)

    def write_one_frame(self):
        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (before adding frame)!")
        if len(self._frames_to_write) == 0:
            return
        frame = self._frames_to_write.pop(0)
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
        logger.debug(
            f"Initialized VideoWriter for camera {frame.camera_id} - Video file will be saved to {video_file_path}")
        return writer

    def close(self):
        self.video_writer.release()
        logger.debug(f"Closed VideoSaver for camera {self.camera_id} - Video file saved to {self.video_path}")
