import logging
import multiprocessing
from multiprocessing import Process
from time import sleep
from typing import Dict, List, Union

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

FRAMES_TO_SAVE_PER_CHUNK = 100
NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE = FRAMES_TO_SAVE_PER_CHUNK * 1.2  # how large the list must be before we start saving

logger = logging.getLogger(__name__)


class VideoSaveBackgroundProcess:

    def __init__(self,
                 frame_dictionaries: Dict[str, Dict[str, Union[str, List[FramePayload]]]],
                 currently_recording_frames: multiprocessing.Value,

                 ):
        self._frame_dictionaries = frame_dictionaries
        self._currently_recording_frames = currently_recording_frames
        self._process = Process(
            name="VideoSaveBackgroundProcess",
            target=VideoSaveBackgroundProcess._begin,
            args=(self._frame_dictionaries, self._currently_recording_frames),
        )


    def start(self):
        self._process.start()


    @staticmethod
    def _begin(frame_lists_by_file_path: Dict[str, List[FramePayload]],
               drain_the_lists_now: multiprocessing.Value):
        logger.info("Starting VideoSaveBackgroundProcess")
        video_recorders = {}
        while True:
            sleep(3)
            frame_list_lengths = [len(frame_list) for frame_list in frame_lists_by_file_path.values()]
            if any([l > NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE for l in
                    frame_list_lengths]) or drain_the_lists_now.value:

                logger.debug(f"Streaming: {frame_list_lengths} frames to video files")
                for file_path, frame_list in frame_lists_by_file_path.items():
                    if drain_the_lists_now.value:
                        logger.info(f"Draining {file_path} of {len(frame_list)} frames")
                        frame_chunk = frame_lists_by_file_path.pop(file_path)
                    else:
                        frame_chunk = frame_lists_by_file_path[file_path][:FRAMES_TO_SAVE_PER_CHUNK]
                        del frame_lists_by_file_path[file_path][:FRAMES_TO_SAVE_PER_CHUNK]

                    if file_path not in video_recorders:
                        video_recorders[file_path] = VideoRecorder(file_path)

                    video_recorders[file_path].save_frame_chunk_to_video_file(frame_chunk,
                                                                              final_chunk=drain_the_lists_now.value)

            if not multiprocessing.parent_process().is_alive():
                logger.info("Parent process is dead. Exiting")
                break
