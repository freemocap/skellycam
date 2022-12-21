import logging
import time
from copy import deepcopy
from multiprocessing import Process
from pathlib import Path
from typing import Dict, List, Union

import cv2
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam.opencv.group.camera_group import CameraGroup
from skellycam.opencv.video_recorder.save_synchronized_videos import (
    save_synchronized_videos,
)
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.qt_gui.workers.save_videos_worker import SaveVideosWorker
from skellycam.system.environment.default_paths import (
    default_base_folder,
    default_session_name,
)

logger = logging.getLogger(__name__)


class CamGroupFrameWorker(QThread):
    ImageUpdate = pyqtSignal(CameraId, QImage)
    cameras_connected_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)

    def __init__(
        self,
        camera_ids: Union[List[str], None],
        session_folder_path: Union[str, Path] = None,
        parent=None,
    ):

        self._updating_camera_settings_bool = False
        self._recording_id = None
        self._video_save_process = None
        logger.info(
            f"Initializing camera group frame worker with camera ids: {camera_ids}"
        )
        super().__init__(parent=parent)

        if session_folder_path is None:
            self._session_folder_path = (
                Path(default_base_folder()) / default_session_name()
            )
        else:
            self._session_folder_path = Path(session_folder_path)

        self._should_pause_bool = False
        self._should_record_frames_bool = False
        self._camera_ids = camera_ids

        if self._camera_ids is not None:
            self._camera_group = self._create_camera_group(self._camera_ids)
            self._video_recorder_dictionary = (
                self._initialize_video_recorder_dictionary()
            )
        else:
            self._camera_group = None
            self._video_recorder_dictionary = None

    @property
    def camera_ids(self):
        return self._camera_ids

    @camera_ids.setter
    def camera_ids(self, camera_ids: List[str]):
        self._camera_ids = camera_ids

        if self._camera_ids is not None:
            if self._camera_group is not None:
                while self._camera_group.is_capturing:
                    self._camera_group.close()
                    time.sleep(0.1)

        self._camera_group = self._create_camera_group(self._camera_ids)
        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()

    @property
    def slot_dictionary(self):
        """
        dictionary of slots to attach to signals in QtMultiCameraControllerWidget
        NOTE - `keys` must match those in QtMultiCameraControllerWidget.button_dictionary
        """
        return {
            "play": self.play,
            "pause": self.pause,
            "start_recording": self.start_recording,
            "stop_recording": self.stop_recording,
        }

    @property
    def camera_config_dictionary(self):
        return self._camera_group.camera_config_dictionary

    def run(self):
        logger.info("Starting camera group frame worker")
        self._camera_group.start()
        should_continue = True

        logger.info("Emitting `cameras_connected_signal`")
        self.cameras_connected_signal.emit()

        while self._camera_group.is_capturing and should_continue:
            if self._updating_camera_settings_bool:
                continue

            frame_obj = self._camera_group.latest_frames()
            for camera_id, frame in frame_obj.items():
                if frame:
                    if not self._should_pause_bool:
                        if self._should_record_frames_bool:
                            self._video_recorder_dictionary[
                                camera_id
                            ].append_frame_payload_to_list(frame)

                        qimage = self._convert_frame(frame)
                        self.ImageUpdate.emit(camera_id, qimage)

            # print(f"camera:recorder_frame_count - {self._get_recorder_frame_count_dict()}")

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
        return converted_frame.scaled(426, 240, Qt.AspectRatioMode.KeepAspectRatio)

    def close(self):
        logger.info("Closing camera group")
        try:
            self._camera_group.close()
        except AttributeError:
            pass

    def pause(self):
        logger.info("Pausing image display")
        self._should_pause_bool = True

    def play(self):
        logger.info("Resuming image display")
        self._should_pause_bool = False

    def start_recording(self):
        logger.info("Starting recording")
        self._recording_id = self._generate_recording_id()
        self._should_record_frames_bool = True

    def stop_recording(self):
        logger.info("Stopping recording")
        self._should_record_frames_bool = False

        self._launch_save_video_process()

    def update_camera_group_configs(self, camera_config_dictionary: dict):
        if self._camera_ids is None:
            self._camera_ids = list(camera_config_dictionary.keys())

        if self._camera_group is None:
            self._camera_group = self._create_camera_group(
                camera_ids=self.camera_ids,
                camera_config_dictionary=camera_config_dictionary,
            )
            return

        self._updating_camera_settings_bool = True
        self._updating_camera_settings_bool = not self._update_camera_settings(
            camera_config_dictionary
        )

    def _launch_save_video_process(self):
        logger.info("Launching save video process")
        if self._video_save_process is not None:
            while self._video_save_process.is_alive():
                time.sleep(0.1)
                logger.info(
                    f"Waiting for video save process to finish: {self._video_save_process}"
                )

        recording_folder_path_string = str(
            Path(self._session_folder_path / self._recording_id)
        )
        self._video_save_process = Process(
            name=f"VideoSaveProcess",
            target=save_synchronized_videos,
            args=(
                deepcopy(self._video_recorder_dictionary),
                recording_folder_path_string,
                True,
            ),
        )
        self._video_save_process.start()
        del self._video_recorder_dictionary
        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()

    def _initialize_video_recorder_dictionary(self):
        return {camera_id: VideoRecorder() for camera_id in self._camera_ids}

    def _generate_recording_id(self) -> str:
        return time.strftime("%H_%M_%S_recording")

    def _get_recorder_frame_count_dict(self):
        return {
            camera_id: recorder.number_of_frames
            for camera_id, recorder in self._video_recorder_dictionary.items()
        }

    def _create_camera_group(
        self, camera_ids: List[Union[str, int]], camera_config_dictionary: dict = None
    ):
        logger.info(
            f"Creating `camera_group` for camera_ids: {camera_ids}, camera_config_dictionary: {camera_config_dictionary}"
        )

        camera_group = CameraGroup(
            camera_ids_list=camera_ids,
            camera_config_dictionary=camera_config_dictionary,
        )
        self.camera_group_created_signal.emit(camera_group.camera_config_dictionary)
        return camera_group

    def _update_camera_settings(self, camera_config_dictionary: dict):
        try:
            self._camera_group.update_camera_configs(camera_config_dictionary)

        except Exception as e:
            logger.error(f"Problem updating camera settings: {e}")

        return True
