import logging
import time
from copy import deepcopy
from typing import List, Union

import cv2
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QImage
from skellycam.detection.charuco.charuco_definition import CharucoBoardDefinition
from skellycam.detection.charuco.charuco_detection import draw_charuco_on_image

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.gui.qt.workers.video_save_thread_worker import VideoSaveThreadWorker
from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam.opencv.group.camera_group import CameraGroup
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


class CamGroupThreadWorker(QThread):
    new_image_signal = Signal(CameraId, QImage, dict)
    cameras_connected_signal = Signal()
    cameras_closed_signal = Signal()
    camera_group_created_signal = Signal(dict)
    videos_saved_to_this_folder_signal = Signal(str)

    def __init__(
            self,
            camera_ids: Union[List[str], None],
            get_new_synchronized_videos_folder_callable: callable,
            annotate_images: bool = False,
            parent=None,
    ):

        self._synchronized_video_folder_path = None
        logger.info(
            f"Initializing camera group frame worker with camera ids: {camera_ids}"
        )
        super().__init__(parent=parent)
        self._camera_ids = camera_ids
        self._get_new_synchronized_videos_folder_callable = get_new_synchronized_videos_folder_callable
        self.annotate_images = annotate_images

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

    @property
    def is_recording(self):
        return self._should_record_frames_bool

    def run(self):
        logger.info("Starting camera group thread worker")
        self._camera_group.start()
        should_continue = True

        logger.info("Emitting `cameras_connected_signal`")
        self.cameras_connected_signal.emit()

        if self.annotate_images:
            charuco_board = CharucoBoardDefinition()

        while self._camera_group.is_capturing and should_continue:
            if self._updating_camera_settings_bool:
                continue

            frame_payload_dictionary = self._camera_group.latest_frames()
            for camera_id, frame_payload in frame_payload_dictionary.items():
                if frame_payload:
                    if not self._should_pause_bool:
                        if self._should_record_frames_bool:
                            self._video_recorder_dictionary[camera_id].append_frame_payload_to_list(frame_payload)
                            logger.info(f"camera:frame_count - {self._get_recorder_frame_count_dict()}")

                        if self.annotate_images:
                            draw_charuco_on_image(image=frame_payload.image, charuco_board=charuco_board)

                        q_image = self._convert_frame(frame_payload)

                        frame_diagnostic_dictionary = {}
                        frame_diagnostic_dictionary["mean_frames_per_second"] = frame_payload.mean_frames_per_second,
                        frame_diagnostic_dictionary["frames_received"] = frame_payload.number_of_frames_received,
                        frame_diagnostic_dictionary["queue_size"] = self._camera_group.queue_size[camera_id]

                        try:
                            frame_diagnostic_dictionary["frames_recorded"] = self._video_recorder_dictionary[
                                camera_id].number_of_frames
                        except KeyError:
                            frame_diagnostic_dictionary["frames_recorded"] = 0
                        except Exception as e:
                            logger.error(f"Error getting frame count for camera {camera_id}: {e}")

                        self.new_image_signal.emit(camera_id, q_image, frame_diagnostic_dictionary)

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

        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()
        self._updating_camera_settings_bool = True
        self._updating_camera_settings_bool = not self._update_camera_settings(
            camera_config_dictionary
        )

    def _launch_save_video_thread_worker(self):
        logger.info("Launching save video thread worker")

        synchronized_videos_folder = self._synchronized_video_folder_path
        self._synchronized_video_folder_path = None

        video_recorders_to_save = {}
        for camera_id, video_recorder in self._video_recorder_dictionary.items():
            if video_recorder.number_of_frames > 0:
                video_recorders_to_save[camera_id] = deepcopy(video_recorder)

        self._video_save_thread_worker = VideoSaveThreadWorker(
            dictionary_of_video_recorders=video_recorders_to_save,
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

    def _initialize_video_recorder_dictionary(self):
        video_recorder_dictionary = {}
        for camera_id, config in self._camera_group.camera_config_dictionary.items():
            if config.use_this_camera:
                video_recorder_dictionary[camera_id] = VideoRecorder()
        return video_recorder_dictionary

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
