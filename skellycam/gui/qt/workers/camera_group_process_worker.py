import logging
import multiprocessing
import time
from copy import deepcopy
from multiprocessing import Process
from pathlib import Path
from typing import List, Union

import cv2
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QWidget

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.gui.qt.workers.video_save_thread_worker import VideoSaveThreadWorker
from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam.opencv.group.camera_group import CameraGroup
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


class CamGroupProcessWorker(QWidget):
    new_image_signal = pyqtSignal(CameraId, QImage, dict)
    cameras_connected_signal = pyqtSignal()
    cameras_closed_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    videos_saved_to_this_folder_signal = pyqtSignal(str)

    def __init__(
            self,
            camera_ids: Union[List[str], None],
            get_new_synchronized_videos_folder_callable: callable,
            parent=None,
    ):

        self._synchronized_video_folder_path = None
        logger.info(
            f"Initializing camera group frame worker with camera ids: {camera_ids}"
        )
        super().__init__(parent=parent)
        self._camera_ids = camera_ids
        self._get_new_synchronized_videos_folder_callable = get_new_synchronized_videos_folder_callable

        self._should_pause_bool = False
        self._should_record_frames_bool = False

        self._updating_camera_settings_bool = False
        self._current_recording_name = None
        self._video_save_process = None

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

    @property
    def cameras_connected(self):
        return self._camera_group.is_capturing

    def start(self):
        self._camera_group_process = Process(target=self._run_camera_group_process)
        self._camera_group_process.start()

    @staticmethod
    def _run_camera_group_process(
            camera_group: CameraGroup,
            synchronized_video_folder_path: Union[str, Path],
            new_image_signal: pyqtSignal,
            cameras_connected_signal: pyqtSignal,
            cameras_closed_signal: pyqtSignal,
            camera_configs_queue: multiprocessing.Queue
    ):
        logger.info("Starting camera group process")
        try:
            camera_group.start()

            should_continue = True

            logger.info("Emitting `cameras_connected_signal`")
            cameras_connected_signal.emit()

            while camera_group.is_capturing and should_continue:
                if self._updating_camera_settings_bool:
                    continue

                multi_frame_payload_dictionary = camera_group.latest_frames()
                for camera_id, frame_payload in multi_frame_payload_dictionary.items():
                    if frame_payload:
                        if not self._should_pause_bool:
                            if self._should_record_frames_bool:
                                self._video_recorder_dictionary[camera_id].append_frame_payload_to_list(frame_payload)
                            q_image = self._convert_frame(frame_payload)

                            frame_diagnostic_dictionary = {}
                            frame_diagnostic_dictionary[
                                "mean_frames_per_second"] = frame_payload.mean_frames_per_second,
                            frame_diagnostic_dictionary["frames_received"] = frame_payload.number_of_frames_received,
                            frame_diagnostic_dictionary["queue_size"] = self._camera_group.queue_size[camera_id]

                            try:
                                frame_diagnostic_dictionary["frames_recorded"] = self._video_recorder_dictionary[
                                    camera_id].number_of_frames
                            except KeyError:
                                frame_diagnostic_dictionary["frames_recorded"] = 0
                            except Exception as e:
                                logger.error(f"Error getting frame count for camera {camera_id}: {e}")

                            new_image_signal.emit(camera_id, q_image, frame_diagnostic_dictionary)
        finally:
            logger.info("Closing camera group process")
            camera_group.close(cameras_closed_signal=cameras_closed_signal)

    @staticmethod
    def _convert_frame(frame: FramePayload):
        image = frame.image
        # image = cv2.flip(image, 1)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        converted_frame = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QImage.Format.Format_RGB888,
        )

        return converted_frame.scaled(int(image.shape[1] / 2), int(image.shape[0] / 2),
                                      Qt.AspectRatioMode.KeepAspectRatio)

    def close(self):
        logger.info("Closing camera group")
        try:
            self._camera_group.close(cameras_closed_signal=self.cameras_closed_signal)
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
        if self.cameras_connected:
            if self._synchronized_video_folder_path is None:
                self._synchronized_video_folder_path = self._get_new_synchronized_videos_folder_callable()
            self._should_record_frames_bool = True
        else:
            logger.warning("Cannot start recording - cameras not connected")

    def stop_recording(self):
        logger.info("Stopping recording")
        self._should_record_frames_bool = False

        self._launch_save_video_thread_worker()
        # self._launch_save_video_process()
        del self._video_recorder_dictionary
        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()

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

    def _launch_save_video_thread_worker(self):
        logger.info("Launching save video thread worker")

        synchronized_videos_folder = self._synchronized_video_folder_path
        self._synchronized_video_folder_path = None

        self._video_save_thread_worker = VideoSaveThreadWorker(
            dictionary_of_video_recorders=deepcopy(self._video_recorder_dictionary),
            folder_to_save_videos=str(synchronized_videos_folder),
            create_diagnostic_plots_bool=True,
        )
        self._video_save_thread_worker.start()
        self._video_save_thread_worker.finished_signal.connect(
            self._handle_videos_save_thread_worker_finished
        )

    def _handle_videos_save_thread_worker_finished(self, folder_path: str):
        logger.debug(f"Emitting `videos_saved_to_this_folder_signal` with string: {folder_path}")
        self.videos_saved_to_this_folder_signal.emit(folder_path)

    #
    # def _launch_save_video_process(self):
    #     logger.info("Launching save video process")
    #     if self._video_save_process is not None:
    #         while self._video_save_process.is_alive():
    #             time.sleep(0.1)
    #             logger.info(
    #                 f"Waiting for video save process to finish: {self._video_save_process}"
    #             )
    #
    #     synchronized_videos_folder = self._synchronized_video_folder_path
    #     self._synchronized_video_folder_path = None
    #     self._video_save_process = Process(
    #         name=f"VideoSaveProcess",
    #         target=save_synchronized_videos,
    #         args=(
    #             deepcopy(self._video_recorder_dictionary),
    #             synchronized_videos_folder,
    #             True,
    #             self.videos_saved_to_this_folder_signal
    #         ),
    #     )
    #     logger.info(f"Launching video save process: {self._video_save_process}")
    #
    #     self._video_save_process.start()
    #     self._video_save_thread_worker.finished_signal.connect(
    #         lambda: self.videos_saved_to_this_folder_signal.emit
    #     )

    def _initialize_video_recorder_dictionary(self):
        return {camera_id: VideoRecorder() for camera_id in self._camera_ids}

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
