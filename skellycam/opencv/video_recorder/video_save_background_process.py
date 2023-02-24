import logging
import multiprocessing
from copy import deepcopy
from multiprocessing import Process
from pathlib import Path
from time import sleep
from typing import Dict, List

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.save_synchronized_videos import save_synchronized_videos
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder

FRAMES_TO_SAVE_PER_CHUNK = 100
NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE = FRAMES_TO_SAVE_PER_CHUNK * 1.2  # how large the list must be before we start saving

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
               video_save_paths: Dict[str, str],
               currently_recording_frames: multiprocessing.Value,
               save_all_at_the_end: bool = True):
        logger.info("Starting VideoSaveBackgroundProcess")
        video_recorders = {}
        while True:
            sleep(1)
            print("VIDEO SAVE PROCESS - WAKING UP WOW")
            final_chunk = False
            for camera_id, frame_list in frame_lists_by_camera.items():

                frame_chunk = None
                frame_list_length = len(frame_list)
                print(f"VIDEO SAVE PROCESS - {camera_id} has {frame_list_length} frames in the list")

                if not save_all_at_the_end:
                    if frame_list_length > NUMBER_OF_FRAMES_NEEDED_TO_TRIGGER_SAVE:
                        print("YUM YUM SAVING FRAMES")
                        frame_chunk = deepcopy(frame_list[:FRAMES_TO_SAVE_PER_CHUNK])
                        del frame_list[:FRAMES_TO_SAVE_PER_CHUNK]
                    else:
                        print("NOT ENOUGH FRAMES TO SAVE")

                if not currently_recording_frames.value and frame_list_length > 0:
                    logger.debug(f"Grabbing {len(frame_list)} frames from Camera {camera_id} to save to video files")
                    frame_chunk = deepcopy(frame_list)
                    del frame_list[:]
                    final_chunk = True
                    if save_all_at_the_end:
                        video_recorders[camera_id] = VideoRecorder()
                        video_recorders[camera_id].frame_list = frame_chunk

                if frame_chunk:
                    if not save_all_at_the_end:
                        video_file_save_path = video_save_paths[camera_id]

                        if video_file_save_path not in video_recorders:
                            logger.debug(f"Creating VideoRecorder for {video_file_save_path}")
                            video_recorders[video_file_save_path] = VideoRecorder(
                                video_file_save_path=video_file_save_path)

                        logger.debug(f"Saving {frame_list_length} frames to video files")
                        video_recorders[video_file_save_path].save_frame_chunk_to_video_file(frame_chunk,
                                                                                             final_chunk=final_chunk)

            if final_chunk:
                logger.debug(f"Saving frames to video files...")
                synchronized_videos_folder = Path(
                    video_save_paths['0']).parent  # hacky ugly shoe-horn to reimplement old save method

                save_synchronized_videos(
                    dictionary_of_video_recorders=video_recorders,
                    folder_to_save_videos=synchronized_videos_folder,
                    create_diagnostic_plots_bool=True,
                )

                logger.info(
                    f"`Saved synchronized videos to folder: {str(synchronized_videos_folder)}")

            if not multiprocessing.parent_process().is_alive():
                logger.info("Parent process is dead. Exiting")
                break
