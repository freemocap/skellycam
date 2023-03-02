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
                 dump_frames_to_video_event: multiprocessing.Event,

                 ):
        self._frame_lists_by_camera = frame_lists_by_camera
        self._video_save_paths_by_camera = video_save_paths_by_camera
        self._dump_frames_to_video_event = dump_frames_to_video_event
        self._process = Process(
            name="VideoSaveBackgroundProcess",
            # target=save_per_chunk_process,
            target=self._start_save_all_at_end_process,
            args=(self._frame_lists_by_camera,
                  self._video_save_paths_by_camera,
                  self._dump_frames_to_video_event),
        )

    @staticmethod
    def _start_save_all_at_end_process(frame_lists_by_camera: Dict[str, List[FramePayload]],
                                       video_save_paths_by_camera: Dict[str, str],
                                       dump_frames_to_video_event: multiprocessing.Event,
                                       ):
        save_all_at_end_process(
            frame_lists_by_camera=frame_lists_by_camera,
            video_save_paths_by_camera=video_save_paths_by_camera,
            dump_frames_to_video_event=dump_frames_to_video_event,
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
