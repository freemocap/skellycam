import logging
import multiprocessing
import time
from copy import deepcopy
from typing import List

import numpy as np
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtGui import QImage

from skellycam.backend.backend_process_controller import BackendController
from skellycam.backend.opencv.camera.types.camera_id import CameraId
from skellycam.backend.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.frontend.qt_gui.workers.video_save_thread_worker import VideoSaveThreadWorker

logger = logging.getLogger(__name__)


class CameraGroupThreadWorker(QThread):
    new_image_signal = pyqtSignal(CameraId, QImage, dict)
    cameras_connected_signal = pyqtSignal()
    cameras_closed_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    videos_saved_to_this_folder_signal = pyqtSignal(str)

    def __init__(
            self,
            camera_ids: List[int],
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

        # self._should_pause_bool = False
        # self._should_record_frames_bool = False

        self._updating_camera_settings_bool = False
        self._current_recording_name = None
        self._video_save_process = None

        self._camera_group = None
        self._video_recorder_dictionary = None

        self._queue = None

    @property
    def camera_ids(self):
        return self._camera_ids

    @camera_ids.setter
    def camera_ids(self, camera_ids: List[int]):
        self._camera_ids = camera_ids

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
        self._queue = multiprocessing.Queue()
        exit_event = multiprocessing.Event()
        backend_controller = BackendController(camera_ids=self.camera_ids,
                                               queue=self._queue,
                                               exit_event=exit_event)
        backend_controller.start_camera_group_process()
        while not exit_event.is_set():
            if not self._queue.empty():
                message = self._queue.get()
                self._handle_queue_message(message)
            else:
                time.sleep(0.001)

    def _handle_queue_message(self, message):
        logger.trace(f"Handling message from backend process with type: {message['type']}")
        if message["type"] == "new_image":
            self._handle_new_image(message["image"], message["frame_info"])

        elif message["type"] == "cameras_connected":
            self.cameras_connected_signal.emit()

        elif message["type"] == "cameras_closed":
            self.cameras_closed_signal.emit()

        elif message["type"] == "camera_group_created":
            self.camera_group_created_signal.emit(message["camera_config_dictionary"])

        elif message["type"] == "videos_saved_to_this_folder":
            self.videos_saved_to_this_folder_signal.emit(message["folder_path"])

        else:
            logger.error(f"Received unknown message from backend process: {message}")

    def _handle_new_image(self, image: np.ndarray, frame_info: dict):

        try:
            q_image = image_to_q_image(image)
            logger.trace(
                f"Emitting `new_image_signal` with camera id: {frame_info['camera_id']} - {image.shape} - frame_stats: {frame_info}")
            self.new_image_signal.emit(frame_info["camera_id"], q_image, frame_info)
        except Exception as e:
            logger.error(f"Problem converting frame: {e}")
            raise e

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

    def _update_camera_settings(self, camera_config_dictionary: dict):
        try:
            self._camera_group.update_camera_configs(camera_config_dictionary)

        except Exception as e:
            logger.error(f"Problem updating camera settings: {e}")

        return True


def image_to_q_image(image: np.ndarray) -> QImage:
    q_image = QImage(
        image.data,
        image.shape[1],
        image.shape[0],
        QImage.Format.Format_RGB888,
    )
    return q_image
