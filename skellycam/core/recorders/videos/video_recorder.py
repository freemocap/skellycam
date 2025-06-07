import logging
from collections import deque
from pathlib import Path

import cv2
from pydantic import BaseModel, ValidationError

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types import CameraIdString

logger = logging.getLogger(__name__)


class VideoRecorder(BaseModel):
    camera_id: CameraIdString
    video_path: str
    camera_config: CameraConfig
    video_file_path: str
    previous_frame: FramePayload|None = None
    frames_to_write: deque[FramePayload] = deque()
    video_writer: cv2.VideoWriter|None  = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def number_of_frames_to_write(self) -> int:
        return len(self.frames_to_write)

    @classmethod
    def create(cls,
               camera_id: CameraIdString,
               recording_info: RecordingInfo,
               config: CameraConfig,
               ):

        video_file_path = str(
            Path(recording_info.videos_folder) / f"{recording_info.recording_name}.camera{config.camera_index}.{config.camera_id}.{config.video_file_extension}")
        Path(video_file_path).parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Created VideoSaver for camera {config.camera_index} with video file path: {video_file_path}")
        return cls(camera_id=camera_id,
                   video_path=video_file_path,
                   camera_config=config,
                   video_file_path=video_file_path
                   )

    def add_frames(self, frames: list[FramePayload]):
        """
        Adds multiple frames to the video recorder.
        :param frames: List of FramePayloads to add.
        """
        for frame in frames:
            self.add_frame(frame=frame)

    def add_frame(self, frame: FramePayload):
        self._validate_frame(frame)
        self.frames_to_write.append(frame)

    def write_one_frame(self) -> int | None:
        if len(self.frames_to_write) == 0:
            return None
        if self.video_writer is None:
            self._initialize_video_writer()

        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (before adding frame)!")

        frame = self.frames_to_write.popleft()
        self._validate_frame(frame)
        if self.previous_frame is not None:
            if not frame.frame_number == self.previous_frame.frame_number + 1:
                raise ValidationError(f"Frame numbers for camera {self.camera_id} are not consecutive! \n "
                                      f"Previous frame number: {self.previous_frame.frame_number}, \n"
                                      f"Current frame number: {frame.frame_number}\n")
        self.previous_frame = frame
        self.video_writer.write(frame.image)
        logger.loop(
            f"VideoRecorder for Camera {self.camera_id} wrote frame {frame.frame_number} to video file: {self.video_path}")

        if not self.video_writer.isOpened():
            raise ValidationError(f"VideoWriter not open (after adding frame)!")
        return frame.frame_number

    def finish_and_close(self):
        logger.debug(f"Finishing and closing VideoSaver for camera {self.camera_id}")
        while len(self.frames_to_write) > 0:
            self.write_one_frame()
        self.close()


    def _initialize_video_writer(self):
        self.video_writer = cv2.VideoWriter(
            self.video_file_path,  # full path to video file
            cv2.VideoWriter_fourcc(*self.camera_config.writer_fourcc),  # fourcc
            self.camera_config.framerate,  # fps
            (self.camera_config.resolution.width, self.camera_config.resolution.height),# frame size, note this is OPPOSITE of most of the rest of cv2's functions, which assume 'height, width' following numpy's row-major order
        )
        if not self.video_writer.isOpened():
            logger.error(f"Failed to open video writer for camera {self.camera_config.camera_index}")
            raise RuntimeError(f"Failed to open video writer for camera {self.camera_config.camera_index}")
        logger.debug(
            f"Initialized VideoWriter for camera {self.camera_config.camera_index} - Video file will be saved to {self.video_file_path}")


    def _validate_frame(self, frame: FramePayload):
        if not Path(self.video_path).parent.exists():
            Path(self.video_path).parent.mkdir(parents=True, exist_ok=True)
        if frame.camera_id != self.camera_config.camera_index:
            raise ValidationError(
                f"Frame camera_id {frame.camera_id} does not match self.camera_config camera_id {self.camera_config.camera_index}")
        if frame.image.shape != self.camera_config.image_shape:
            raise ValidationError(f"Frame shape ({frame.image.shape}) does not match expected shape ({self.camera_config.image_shape})")

    def close(self):
        if self.video_writer:
            self.video_writer.release()
            logger.debug(f"Closed VideoSaver for camera {self.camera_id} - Video file saved to {self.video_path}")
