import logging
import multiprocessing
from multiprocessing import Process
from typing import Dict, List

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.video_save_background_process.save_processes.save_all_at_end_process import \
    save_all_at_end_process

logger = logging.getLogger(__name__)


class VideoSaveBackgroundProcess:

    def __init__(self,
                 frame_lists_by_camera: Dict[str, List[FramePayload]],
                 video_save_paths_by_camera: Dict[str, str],
                 currently_recording_frames: multiprocessing.Value,

                 ):
        self._frame_lists_by_camera = frame_lists_by_camera
        self._video_save_paths_by_camera = video_save_paths_by_camera
        self._currently_recording_frames = currently_recording_frames
        self._process = Process(
            name="VideoSaveBackgroundProcess",
            # target=save_per_chunk_process,
            target=self._start_save_all_at_end_process,
            args=(self._frame_lists_by_camera,
                  self._video_save_paths_by_camera,
                  self._currently_recording_frames),
        )

    @staticmethod
    def _start_save_all_at_end_process(frame_lists_by_camera: Dict[str, List[FramePayload]],
                                       video_save_paths_by_camera: Dict[str, str],
                                       currently_recording_frames: multiprocessing.Value,
                                       ):
        save_all_at_end_process(
            frame_lists_by_camera=frame_lists_by_camera,
            video_save_paths_by_camera=video_save_paths_by_camera,
            currently_recording_frames=currently_recording_frames,
        )

    @property
    def is_alive(self):
        return self._process.is_alive()

    def start(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._process.start()

    def terminate(self):
        logger.info("Terminating VideoSaveBackgroundProcess")
        self._process.terminate()
