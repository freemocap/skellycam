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
                 folder_to_save_videos: List[str],
                 dump_frames_to_video_event: multiprocessing.Event,

                 ):

        self._process = Process(
            name="VideoSaveBackgroundProcess",
            # target=save_per_chunk_process,
            target=self._start_save_all_at_end_process,
            args=(frame_lists_by_camera,
                  folder_to_save_videos,
                  dump_frames_to_video_event),
        )

    @staticmethod
    def _start_save_all_at_end_process(frame_lists_by_camera: Dict[str, List[FramePayload]],
                                       folder_to_save_videos: multiprocessing.Value,
                                       dump_frames_to_video_event: multiprocessing.Event,
                                       ):
        save_all_at_end_process(
            frame_lists_by_camera=frame_lists_by_camera,
            folder_to_save_videos=folder_to_save_videos,
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
