from pathlib import Path
from typing import List

import cv2

from skellycam import logger
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frames.frame_payload import FramePayload


class VideoRecorder:
    def __init__(self,
                 camera_config: CameraConfig,
                 video_save_path: str,
                 ):
        self._camera_config = camera_config
        self._video_save_path = Path(video_save_path)
        self._cv2_video_writer = self._create_video_writer()
        self._timestamp_file = self._initialize_timestamp_writer()
        self._frame_payload_list: List[FramePayload] = []
        self._first_frame_timestamp = None

    def close(self):
        self._cv2_video_writer.release()
        self._timestamp_file.close()

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        if self._first_frame_timestamp is None:
            self._first_frame_timestamp = frame_payload.timestamp_ns
        self._frame_payload_list.append(frame_payload)

    def one_frame_to_disk(self):
        if len(self._frame_payload_list) == 0:
            return
        frame = self._frame_payload_list.pop(-1)
        self._cv2_video_writer.write(frame.image)
        timestamp_from_zero = frame.timestamp_ns - self._first_frame_timestamp
        self._timestamp_file.write(f"{frame.frame_number}, {timestamp_from_zero}\n")

    def finish_and_close(self):
        self.finish()
        self.close()

    def finish(self):
        while len(self._frame_payload_list) > 0:
            self.one_frame_to_disk()

    def _create_video_writer(
            self,
            fourcc: str = "mp4v",
    ) -> cv2.VideoWriter:
        logger.debug(
            f"Creating video writer for camera {self._camera_config.camera_id} to save video at: {self._video_save_path}")
        self._video_save_path.parent.mkdir(parents=True, exist_ok=True)
        video_writer_object = cv2.VideoWriter(
            str(self._video_save_path),
            cv2.VideoWriter_fourcc(*self._camera_config.fourcc),
            self._camera_config.framerate,
            (int(self._camera_config.resolution.width),
             int(self._camera_config.resolution.height)),
        )

        if not video_writer_object.isOpened():
            logger.error(f"cv2.VideoWriter failed to initialize!")
            raise Exception("cv2.VideoWriter is not open")

        return video_writer_object

    def _initialize_timestamp_writer(self):

        timestamp_file_path = Path(self._video_save_path.parent) / "timestamps" / Path(
            self._video_save_path.stem + "_timestamps.csv")
        logger.debug(f"Creating timestamp file at: {timestamp_file_path}")
        timestamp_file_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp_file_path.touch(exist_ok=True)
        timestamp_file = open(timestamp_file_path, "w")
        timestamp_file.write("frame_number, timestamp_from_zero_ns\n")
        return timestamp_file
