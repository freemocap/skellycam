import time
from pathlib import Path
from typing import List, Optional, Dict

import cv2

from skellycam.system.environment.get_logger import logger
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
        self._perf_counter_to_unix_mapping: Optional[Dict[int, int]] = None
        self._camera_config = camera_config
        self._video_save_path = Path(video_save_path)

        self._previous_frame_timestamp: Optional[int] = None
        self._initialization_frame: Optional[FramePayload] = None
        self._cv2_video_writer: Optional[cv2.VideoWriter] = None
        self._timestamp_file = None
        self._frame_payload_list: List[FramePayload] = []

    @property
    def has_frames_to_save(self):
        return len(self._frame_payload_list) > 0

    @property
    def finished(self):
        frames_save_done = not self.has_frames_to_save
        video_writer_done = not self._cv2_video_writer.isOpened() if self._cv2_video_writer is not None else True
        return frames_save_done and video_writer_done

    @property
    def first_frame_timestamp(self) -> int:
        return self._initialization_frame.timestamp_ns

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        if self._initialization_frame is None:
            self._initialize_on_first_frame(frame_payload)
        self._frame_payload_list.append(frame_payload)

    def one_frame_to_disk(self):
        if len(self._frame_payload_list) == 0:
            raise AssertionError("No frames to save, but `one_frame_to_disk` was called! "
                                 "There's a buggo in the application logic somewhere...")
        self._check_if_writer_open()
        frame = self._frame_payload_list.pop(-1)
        self._validate_frame(frame=frame)
        image = frame.get_image()
        self._cv2_video_writer.write(image)

    def _check_if_writer_open(self):

        if self._cv2_video_writer is None:
            raise AssertionError("VideoWriter is None, but `_check_if_writer_open` was called! "
                                 "There's a buggo in the application logic somewhere...")

        if not self._cv2_video_writer.isOpened():
            if Path(self._video_save_path).exists():
                raise AssertionError(
                    f"VideoWriter is not open, but video file already exists at {self._video_save_path} - looks like the VideoWriter initialized properly but closed unexpectedly!")
            else:
                raise AssertionError(
                    "VideoWriter is not open and video file doesn't exist - looks like the VideoWriter failed to initialize!")

    def finish_and_close(self):
        self.finish()
        if self.has_frames_to_save:
            raise AssertionError("VideoRecorder `finish` was returned, but there are still frames to save!")
        self.close()

    def finish(self):
        logger.debug(f"Finishing video recording for camera {self._camera_config.camera_id}")
        while len(self._frame_payload_list) > 0:
            self.one_frame_to_disk()

    def close(self):
        logger.debug(f"Closing video recorder for camera {self._camera_config.camera_id}")
        if self.has_frames_to_save:
            raise AssertionError("VideoRecorder has frames to save, but `close` was called! Theres a buggo in the logic somewhere...")
        self._close_video_writer() if self._cv2_video_writer is not None else None

    def _initialize_on_first_frame(self, frame_payload):
        self._initialization_frame = frame_payload.copy(deep=True)
        self._cv2_video_writer = self._create_video_writer()
        self._check_if_writer_open()
        self._previous_frame_timestamp = frame_payload.timestamp_ns

    def _close_video_writer(self):
        logger.debug(
            f"Closing video writer for camera {self._camera_config.camera_id} to save video at: {self._video_save_path}")
        if self._cv2_video_writer is None:
            raise AssertionError(
                "VideoWriter is None, but `_close_video_writer` was called! There's a buggo in the application logic somewhere...")
        self._cv2_video_writer.release()

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
            raise Exception("cv2.VideoWriter failed to initialize!")

        return video_writer_object



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
