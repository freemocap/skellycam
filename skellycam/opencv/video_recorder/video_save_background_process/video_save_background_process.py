import logging
import multiprocessing
from multiprocessing import Process
from time import sleep
from typing import Dict, List

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.opencv.group.strategies.grouped_process.multi_frame_emitter import MultiFrameEmitter
from skellycam.opencv.video_recorder.video_save_background_process.save_processes.stream_save.stream_save import (
    StreamSave,
)

logger = logging.getLogger(__name__)

SECONDS_TO_WAIT_BEFORE_STARTING_STREAM_SAVE = 3  # number of seconds to wait before starting the video saving process, in order to allow enough frames to accumulate that we can get a good estimate of framerate


class VideoSaveBackgroundProcess:
    def __init__(
            self,
            camera_ids: List[str],
            multi_frame_pipe_connection: multiprocessing.Pipe,
            save_folder_path_pipe_connection: multiprocessing.Pipe,
            stop_recording_event: multiprocessing.Event,
    ):
        self._process = Process(
            name="VideoSaveBackgroundProcess",
            # target=self._start_save_all_at_end_process,
            target=self._start_stream_save,
            args=(
                camera_ids,
                multi_frame_pipe_connection,
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
    def _start_stream_save(
            camera_ids: List[str],
            multi_frame_pipe_connection: multiprocessing.Pipe,
            save_folder_path_pipe_connection: multiprocessing.Pipe,
            stop_recording_event: multiprocessing.Event,

    ):
        stream_save = StreamSave(
            camera_ids=camera_ids,
            multi_frame_pipe_connection=multi_frame_pipe_connection,
            stop_recording_event=stop_recording_event,
            save_folder_path_pipe_connection=save_folder_path_pipe_connection,
        )
        stream_save.run()


    @property
    def is_alive(self):
        return self._process.is_alive()

    def start(self):
        logger.info("Starting VideoSaveBackgroundProcess")
        self._process.start()

    def terminate(self):
        logger.info("Terminating VideoSaveBackgroundProcess")
        self._process.terminate()
