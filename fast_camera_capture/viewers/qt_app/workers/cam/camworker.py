import time
from pathlib import Path
from typing import List

import cv2
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage

from fast_camera_capture.detection.models.frame_payload import FramePayload
from fast_camera_capture.opencv.camera.types.camera_id import CameraId
from fast_camera_capture.opencv.group.camera_group import CameraGroup
from fast_camera_capture.opencv.video_recorder.save_synchronized_videos import save_synchronized_videos
from fast_camera_capture.opencv.video_recorder.video_recorder import VideoRecorder
from fast_camera_capture.system.environment.default_paths import default_video_save_path, default_session_name


class CamGroupFrameWorker(QThread):
    ImageUpdate = pyqtSignal(CameraId, QImage)

    def __init__(self, cam_ids: List[str], parent=None):
        super().__init__(parent=parent)
        self._video_save_folder_path = None
        self._record_frames_bool = True
        self._cam_ids = cam_ids
        self._cam_group = CameraGroup(cam_ids)
        self._video_recorder_dictionary = {camera_id: VideoRecorder() for camera_id in cam_ids}

    def run(self):
        max_frames = 100

        recorded_any_frames = False
        should_continue = True

        self._cam_group.start()
        while self._cam_group.is_capturing and should_continue:

            frame_obj = self._cam_group.latest_frames()
            for camera_id, frame in frame_obj.items():
                if frame:

                    if self._record_frames_bool:
                        recorded_any_frames = True
                        self._video_recorder_dictionary[camera_id].append_frame_payload_to_list(frame)

                    print(f"frame number: {self._video_recorder_dictionary[camera_id].number_of_frames}")
                    if self._video_recorder_dictionary[camera_id].number_of_frames >= max_frames:
                        should_continue = False

                    qimage = self._convert_frame(frame)
                    self.ImageUpdate.emit(camera_id, qimage)

        if recorded_any_frames:
            if self._video_save_folder_path is None:
                self._video_save_folder_path = Path(default_video_save_path()) /default_session_name()

            save_synchronized_videos(dictionary_of_video_recorders=self._video_recorder_dictionary,
                                     folder_to_save_videos=self._video_save_folder_path)

    def _convert_frame(self, frame: FramePayload):
        image = frame.image
        # image = cv2.flip(image, 1)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        converted_frame = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QImage.Format.Format_RGB888,
        )
        return converted_frame.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)

    def close(self):
        self._cam_group.close()
