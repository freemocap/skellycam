import logging
from pathlib import Path
from typing import Union

from PyQt6.QtCore import QThread, pyqtSignal

from skellycam.opencv.video_recorder.save_synchronized_videos import (
    save_synchronized_videos,
)

logger = logging.getLogger(__name__)


class SaveVideosWorker(QThread):
    done_saving_videos_signal = pyqtSignal()

    def __init__(
        self, video_recorder_dictionary: dict, save_video_path: Union[str, Path]
    ):
        logger.info(
            f"Initializing save videos worker with session folder path: {save_video_path}"
        )
        super().__init__()
        self._video_recorder_dictionary = video_recorder_dictionary
        self._session_folder_path = Path(save_video_path)

    def run(self):
        logger.info(
            f"Starting save videos worker with session folder path: {self._session_folder_path}"
        )
        save_synchronized_videos(
            self._video_recorder_dictionary, self._session_folder_path
        )
        self.done_saving_videos_signal.emit()
