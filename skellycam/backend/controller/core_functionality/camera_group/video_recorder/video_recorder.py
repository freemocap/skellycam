import time
from pathlib import Path
from typing import List, Optional

import cv2

from skellycam import logger
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frames.frame_payload import FramePayload
from skellycam.system.environment.default_paths import get_default_skellycam_base_folder_path


class FailedToWriteFrameToVideoException(Exception):
    pass

class VideoRecorder:
    def __init__(self,
                 camera_config: CameraConfig,
                 video_save_path: str,
                 ):
        self._initialization_frame: Optional[FramePayload] = None
        self._camera_config = camera_config
        self._video_save_path = Path(video_save_path)
        self._cv2_video_writer: Optional[cv2.VideoWriter] = None
        self._timestamp_file = None
        self._frame_payload_list: List[FramePayload] = []

    @property
    def has_frames_to_save(self):
        return len(self._frame_payload_list) > 0

    @property
    def first_frame_timestamp(self) -> int:
        return self._initialization_frame.timestamp_ns

    def close(self):
        logger.debug(f"Closing video recorder for camera {self._camera_config.camera_id}")
        if self.has_frames_to_save:
            logger.warning(f"Video recorder for camera {self._camera_config.camera_id} has frames to save!")
            self.finish()
        self._cv2_video_writer.release()
        self._timestamp_file.close()

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        if self._initialization_frame is None:
            self._initialize_on_first_frame(frame_payload)
        self._frame_payload_list.append(frame_payload)

    def _initialize_on_first_frame(self, frame_payload):
        self._initialization_frame = frame_payload.copy(deep=True)
        self._cv2_video_writer = self._create_video_writer()
        self._timestamp_file = self._initialize_timestamp_writer()

    def one_frame_to_disk(self):
        if len(self._frame_payload_list) == 0:
            return
        frame = self._frame_payload_list.pop(-1)
        self._validate_frame(frame=frame)
        image = frame.get_image()
        self._cv2_video_writer.write(image)
        timestamp_from_zero = frame.timestamp_ns - self.first_frame_timestamp
        self._timestamp_file.write(f"{frame.frame_number}, {timestamp_from_zero}\n")


    def finish_and_close(self):
        self.finish()
        self.close()

    def finish(self):
        logger.debug(f"Finishing video recording for camera {self._camera_config.camera_id}")
        while len(self._frame_payload_list) > 0:
            self.one_frame_to_disk()

    def _create_video_writer(
            self,
    ) -> cv2.VideoWriter:
        logger.debug(
            f"Creating video writer for camera {self._camera_config.camera_id} to save video at: {self._video_save_path}")
        self._video_save_path.parent.mkdir(parents=True, exist_ok=True)
        video_writer_object = cv2.VideoWriter(
            str(self._video_save_path),
            cv2.VideoWriter_fourcc(*self._camera_config.writer_fourcc),
            self._camera_config.framerate,
            self._initialization_frame.get_resolution()
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

    def _validate_frame(self, frame: FramePayload):
        if frame.get_resolution() != self._initialization_frame.get_resolution():
            raise Exception(
                f"Frame resolution {frame.get_resolution()} does not match initialization frame resolution {self._initialization_frame.get_resolution()}")


def test_video_recording():
    from skellycam.backend.controller.core_functionality.config.determine_backend import determine_backend
    from skellycam.backend.controller.core_functionality.config.apply_config import apply_camera_configuration

    camera_id = 0
    # Initialize a default camera_config
    config = CameraConfig(camera_id=camera_id,
                          writer_fourcc="XVID", )

    cap_backend = determine_backend()

    cap = cv2.VideoCapture(config.camera_id, cap_backend.value)
    apply_camera_configuration(cap, config)

    # Initialize VideoRecorder with camera_config and a save path
    save_path = Path(get_default_skellycam_base_folder_path()) / "tests" / f"test_video_recording_{camera_id}.avi"
    video_recorder = VideoRecorder(config, str(save_path))

    # Record 100 frames
    for frame_number in range(100):
        success, image = cap.read()

        if not success:
            raise Exception(f"Failed to read frame from camera {camera_id}")

        frame_payload = FramePayload.create(success=success,
                                            frame_number=frame_number,
                                            image=image,
                                            camera_id=camera_id,
                                            timestamp_ns=time.perf_counter_ns()
                                            )
        video_recorder.append_frame_payload_to_list(frame_payload)
        video_recorder.one_frame_to_disk()

    # Finish recording, and save the video
    video_recorder.finish_and_close()

    cap.release()
    print("Recording finished.")


if __name__ == "__main__":
    test_video_recording()
