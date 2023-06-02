import logging
import multiprocessing
from multiprocessing import Process
from time import sleep
from typing import Dict, List

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.video_recorder.video_save_background_process.save_processes.save_all_at_end_process import (
    SaveAll,
)
from skellycam.opencv.video_recorder.video_save_background_process.save_processes.save_per_chunk_process import (
    ChunkSave,
)

logger = logging.getLogger(__name__)


class VideoSaveBackgroundProcess:
    def __init__(
            self,
            frame_lists_by_camera: Dict[str, List[FramePayload]],
            save_folder_path_pipe_connection: multiprocessing.Pipe,
            stop_recording_event: multiprocessing.Event,
    ):
        self._process = Process(
            name="VideoSaveBackgroundProcess",
            # target=self._start_save_all_at_end_process,
            target=self._start_save_chunk,
            args=(
                frame_lists_by_camera,
                save_folder_path_pipe_connection,
                stop_recording_event,
            ),
        )

    # @staticmethod
    # def _start_save_all_at_end_process(
    #         frame_lists_by_camera: Dict[str, List[FramePayload]],
    #         save_folder_path_pipe_connection: multiprocessing.Pipe,
    # ):
    #     sa = SaveAll(
    #         frame_lists_by_camera,
    #         save_folder_path_pipe_connection,
    #     )
    #     while True:
    #         sleep(1)
    #         if dump_frames_to_video_event.is_set():
    #             dump_frames_to_video_event.clear()
    #             logger.info("Video Save Process - There are frames to save!")
    #             sa.run()
    #
    #         # TODO: Processes should be managed by the parent.
    #         #  We can set up the SIGINT signal in children to ensure daemon processes
    #         #  respond appropriately.
    #         if not multiprocessing.parent_process().is_alive():
    #             logger.info("Parent process is dead. Exiting")
    #             break

    @staticmethod
    def _start_save_chunk(
            frame_lists_by_camera: Dict[str, List[FramePayload]],
            save_folder_path_pipe_connection: multiprocessing.Pipe,
            stop_recording_event: multiprocessing.Event,

    ):
        cs = ChunkSave(
            frame_lists_by_camera,
            save_folder_path_pipe_connection,
            stop_recording_event
        )
        while True:
            sleep(1)
            print("Checking for frames to save...")
            if save_folder_path_pipe_connection.poll():
                logger.info("Video Save Process - There are frames to save!")
                video_file_paths = save_folder_path_pipe_connection.recv()
                cs.run(video_file_paths=video_file_paths,
                       stop_recording_event=stop_recording_event)


    @property
    def is_alive(self):
        return self._process.is_alive()

    def start(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._process.start()

    def terminate(self):
        logger.info("Terminating VideoSaveBackgroundProcess")
        self._process.terminate()
