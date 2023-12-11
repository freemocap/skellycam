import logging
from pathlib import Path
from typing import Dict, Union

from PySide6.QtCore import Signal, QThread

from skellycam.opencv.video_recorder.save_synchronized_videos import save_synchronized_videos
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


class VideoSaveThreadWorker(QThread):
    finished_signal = Signal(str)

    def __init__(
            self,
            dictionary_of_video_recorders: Dict[str, VideoRecorder],
            folder_to_save_videos: Union[str, Path],
            create_diagnostic_plots_bool: bool = True,

    ):
        super().__init__()
        self._dictionary_of_video_recorders = dictionary_of_video_recorders
        self._folder_to_save_videos = folder_to_save_videos
        self._create_diagnostic_plots_bool = create_diagnostic_plots_bool

    def run(self):
        logger.info(f"Saving synchronized videos to folder: {str(self._folder_to_save_videos)}")

        save_synchronized_videos(
            dictionary_of_video_recorders=self._dictionary_of_video_recorders,
            folder_to_save_videos=self._folder_to_save_videos,
            create_diagnostic_plots_bool=self._create_diagnostic_plots_bool,
        )

        logger.info(
            f"`VideoSaveThreadWorker` finished saving synchronized videos to folder: {str(self._folder_to_save_videos)}")
        self.finished_signal.emit(str(self._folder_to_save_videos))
