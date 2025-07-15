import logging
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


class VideoRecorder(BaseModel):
    camera_id: CameraIdString
    camera_index: int
    video_file_path: str
    video_image_shape: tuple[
        int, int]  # NOTE - this is (width, height) as per OpenCV's convention, which is opposite of numpy's row-major order
    framerate: float
    writer_fourcc: str
    previous_frame_number: int | None = None
    frames_to_write: deque[np.recarray] = deque()
    video_writer: cv2.VideoWriter | None = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def any_data_saved(self) -> bool:
        return self.previous_frame_number is not None

    @property
    def number_of_frames_to_write(self) -> int:
        return len(self.frames_to_write)

    @classmethod
    def create(cls,
               recording_info: RecordingInfo|None,
               config: CameraConfig,
               ):
        if recording_info is None:
            recording_info = RecordingInfo.create_temp()
        video_file_path = recording_info.video_file_path_from_camera_config(config)
        Path(video_file_path).parent.mkdir(parents=True, exist_ok=True)
        if config.rotation.value == -1 or config.rotation.value == cv2.ROTATE_180:
            video_image_shape = config.resolution.width, config.resolution.height  # (width, height) as per OpenCV's convention (NOT numpy's row-major order)

        else:
            video_image_shape = config.resolution.height, config.resolution.width # swap width and height for portrait mode rotations



        logger.debug(f"Created VideoSaver for camera {config.camera_index} with video file path: {video_file_path}")
        instance =  cls(camera_id=config.camera_id,
                        camera_index=config.camera_index,
                        video_file_path=video_file_path,
                        video_image_shape=video_image_shape,
                        framerate=config.framerate,
                        writer_fourcc=config.writer_fourcc,
                        )
        instance._initialize_video_writer()
        return instance

    def record_frame(self, frame: np.recarray):
        self.add_frame(frame)
        self.write_one_frame()

    def add_frame(self, frame: np.recarray):
        self.frames_to_write.append(frame)

    def write_one_frame(self) -> int | None:
        if len(self.frames_to_write) == 0:
            return None
        if self.video_writer is None:
            self._initialize_video_writer()

        if not self.video_writer.isOpened():
            raise ValueError(f"VideoWriter not open (before adding frame)!")

        frame = self.frames_to_write.popleft()
        self._validate_frame_number(frame)
        if frame.frame_metadata.camera_config.rotation != -1:
            image = cv2.rotate(frame.image[0],
                               frame.frame_metadata.camera_config.rotation[0])
        else:
            image = frame.image[0]
        self._validate_image_shape(image)
        logger.api(f"Writing frame {frame.frame_metadata.frame_number[0]} for camera {self.camera_id} to video file")
        self.previous_frame_number = frame.frame_metadata.frame_number[0]

        self.video_writer.write(image)
        if not self.video_writer.isOpened():
            raise ValueError(f"VideoWriter not open (after adding frame)!")
        return frame.frame_metadata.frame_number

    def finish_and_close(self):
        logger.debug(
            f"Finishing and closing VideoSaver for camera {self.camera_id} with {self.number_of_frames_to_write} frames to left write.")
        while len(self.frames_to_write) > 0:
            self.write_one_frame()

        self.close()

    def _initialize_video_writer(self):

        self.video_writer = cv2.VideoWriter(
            self.video_file_path,  # full path to video file
            cv2.VideoWriter_fourcc(*self.writer_fourcc),  # fourcc
            self.framerate,  # fps
            self.video_image_shape,
            # frame size, note this is OPPOSITE of most of the rest of cv2's functions, which assume 'height, width' following numpy's row-major order
        )
        if not self.video_writer.isOpened():
            logger.error(f"Failed to open video writer for camera {self.camera_index}")
            raise RuntimeError(f"Failed to open video writer for camera {self.camera_index}")
        logger.debug(
            f"Initialized VideoRecorder for camera {self.camera_index} - Video file will be saved to {self.video_file_path}")


    def _validate_image_shape(self, image: np.ndarray):
        image_video_shape = (image.shape[1], image.shape[0])
        if image_video_shape != self.video_image_shape:
            raise ValueError(
                f"Frame shape ({image_video_shape}) does not match expected shape ({self.video_image_shape})")

    def _validate_frame_number(self, frame: np.recarray):
        if self.previous_frame_number is not None:
            if not frame.frame_metadata.frame_number[0] == self.previous_frame_number + 1:
                raise ValueError(f"Frame numbers for camera {self.camera_id} are not consecutive! \n "
                                 f"Previous frame number: {self.initial_frame.frame_metadata.frame_number}, \n"
                                 f"Current frame number: {frame.frame_metadata.frame_number}\n")

    # def _validate_rotation(self, frame: np.recarray):
    #     """Validate that rotation hasn't changed mid-recording"""
    #     if self.initial_frame is not None:
    #         current_rotation = frame.frame_metadata.camera_config.rotation
    #         previous_rotation = self.initial_frame.frame_metadata.camera_config.rotation
    #         if current_rotation != previous_rotation:
    #             raise ValueError(f"Rotation changed mid-recording for camera {self.camera_id}! "
    #                              f"Previous rotation: {previous_rotation}, "
    #                              f"Current rotation: {current_rotation}")

    def close(self):
        if self.video_writer:
            self.video_writer.release()
            logger.info(f"Camera {self.camera_id} - Video file saved to {self.video_file_path}")
