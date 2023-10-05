import logging
import multiprocessing
import time
from typing import List, Dict

import numpy as np
from PyQt6.QtCore import pyqtSignal, QThread, QByteArray, pyqtSlot
from PyQt6.QtGui import QImage

from skellycam.backend.backend_process_controller import BackendProcessController
from skellycam.backend.opencv.camera.types.camera_id import CameraId
from skellycam.backend.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.data_models.camera_config import CameraConfig

logger = logging.getLogger(__name__)


class CameraGroupThreadWorker(QThread):
    new_image_signal = pyqtSignal(CameraId, QImage, dict)
    cameras_connected_signal = pyqtSignal()
    cameras_closed_signal = pyqtSignal()
    camera_group_created_signal = pyqtSignal(dict)
    videos_saved_to_this_folder_signal = pyqtSignal(str)

    def __init__(
            self,
            get_new_synchronized_videos_folder_callable: callable,
            parent=None,
    ):
        self._synchronized_video_folder_path = None

        super().__init__(parent=parent)
        self._get_new_synchronized_videos_folder_callable = get_new_synchronized_videos_folder_callable

        self._camera_group = None
        self._annotate_images = None
        self._camera_configs = None
        self._video_recorder_dictionary = None

        self._queue_to_backend = None

    @pyqtSlot()
    def add_message_to_queue(self):
        self._queue_to_backend.put({"type": "get_latest_frames"})

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
    def camera_configs(self):
        return self._camera_group.camera_configs

    @camera_configs.setter
    def camera_configs(self, camera_configs: Dict[str, CameraConfig]):
        self._camera_configs = camera_configs

    @property
    def cameras_connected(self):
        if self._camera_group is None:
            return False
        return self._camera_group.is_capturing

    @property
    def is_recording(self):
        return self._should_record_frames_bool

    def run(self):
        receive_from_frontend, send_to_backend = multiprocessing.Pipe(duplex=False)
        receive_from_backend, send_to_frontend = multiprocessing.Pipe(duplex=False)

        exit_event = multiprocessing.Event()
        backend_controller = BackendProcessController(camera_configs=self._camera_configs,
                                                      send_to_frontend=send_to_frontend,
                                                      receive_from_frontend=receive_from_frontend,
                                                      exit_event=exit_event)

        backend_controller.start_camera_group_process()
        while not exit_event.is_set():
            if  receive_from_backend.poll():
                message = receive_from_backend.recv()
                self._handle_queue_message(message)
            else:
                time.sleep(0.033)
                send_to_backend.send({"type": "get_latest_frames"})

    def _handle_queue_message(self, message):
        logger.trace(f"Handling message from backend process with type: {message['type']}")
        if message["type"] == "new_image":
            self._handle_latest_frames(message["image"], message["frame_info"])

        elif message["type"] == "cameras_connected":
            self.cameras_connected_signal.emit()

        elif message["type"] == "cameras_closed":
            self.cameras_closed_signal.emit()

        elif message["type"] == "camera_group_created":
            self.camera_group_created_signal.emit(message["camera_config_dictionary"])

        elif message["type"] == "videos_saved_to_this_folder":
            self.videos_saved_to_this_folder_signal.emit(message["folder_path"])

        else:
            logger.error(f"Received unknown message type from backend process: `{message['type']}`")

    def _handle_latest_frames(self, image_byte_array: QByteArray, frame_info: dict):

        try:
            q_image = image_byte_string_to_q_image(image_byte_array)
            logger.trace(
                f"Emitting `new_image_signal` with camera id: {frame_info['camera_id']}")
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

    def _initialize_video_recorder_dictionary(self):
        video_recorder_dictionary = {}
        for camera_id, config in self._camera_group.camera_configs.items():
            if config.use_this_camera:
                video_recorder_dictionary[camera_id] = VideoRecorder()
        return video_recorder_dictionary


def image_to_q_image(image: np.ndarray) -> QImage:
    q_image = QImage(
        image.data,
        image.shape[1],
        image.shape[0],
        QImage.Format.Format_RGB888,
    )
    return q_image


def image_byte_string_to_q_image(image_byte_array: QByteArray) -> QImage:
    q_image = QImage()
    q_image.loadFromData(image_byte_array)
    return q_image
