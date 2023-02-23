import logging
import multiprocessing
from copy import deepcopy
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
                 frame_lists_by_camera: Dict[str,List[FramePayload]],
                 video_save_paths_by_camera: Dict[str, str],
                 currently_recording_frames: multiprocessing.Value,

                 ):
        self._frame_lists_by_camera = frame_lists_by_camera
        self._video_save_paths_by_camera = video_save_paths_by_camera
        self._currently_recording_frames = currently_recording_frames
        self._process = Process(
            name="VideoSaveBackgroundProcess",
            target=VideoSaveBackgroundProcess._begin,
            args=(self._frame_lists_by_camera,
                  self._video_save_paths_by_camera,
                  self._currently_recording_frames),
        )

    def start(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._process.start()

    def terminate(self):
        logger.info("Terminating VideoSaveBackgroundProcess")
        self._process.terminate()

    @staticmethod
    def _begin(frame_lists_by_camera: Dict[str, List[FramePayload]],
               video_save_paths : Dict[str, str],
               currently_recording_frames: multiprocessing.Value):
        logger.info("Starting VideoSaveBackgroundProcess")
        video_recorders = {}
        while True:
            sleep(3)
            print("VIDEO SAVE PROCESS - WAKING UP WOW")
            for camera_id, frame_list in frame_lists_by_camera.items():

                frame_chunk = None
                final_chunk = False
                frame_list_length = len(frame_list)
                print(f"VIDEO SAVE PROCESS - {camera_id} has {frame_list_length} frames in the list")

                if frame_list_length > NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE:
                    print("YUM YUM SAVING FRAMES")
                    frame_chunk = deepcopy(frame_list[:FRAMES_TO_SAVE_PER_CHUNK])
                    del frame_list[:FRAMES_TO_SAVE_PER_CHUNK]
                else:
                    print("NOT ENOUGH FRAMES TO SAVE")

                if not currently_recording_frames.value and frame_list_length > 0:
                    logger.debug(f"Clearing last frames and then finalizing video file {video_file_save_path}")
                    frame_chunk = deepcopy(frame_list)
                    frame_lists_by_camera[camera_id] = []
                    final_chunk = True

                if frame_chunk:
                    video_file_save_path = video_save_paths[camera_id]

                    if video_file_save_path not in video_recorders:
                        logger.debug(f"Creating VideoRecorder for {video_file_save_path}")
                        video_recorders[video_file_save_path] = VideoRecorder(video_file_save_path=video_file_save_path)

                    logger.debug(f"Streaming: {frame_list_length} frames to video files")
                    video_recorders[video_file_save_path].save_frame_chunk_to_video_file(frame_chunk,
                                                                                         final_chunk=final_chunk)

            if not multiprocessing.parent_process().is_alive():
                logger.info("Parent process is dead. Exiting")
                break
