import logging
import multiprocessing
from typing import Tuple, Optional

from skellycam.core.cameras.config.camera_configs import CameraConfigs
from skellycam.core.recorder.video_recorder_process import (
    VideoRecorderProcess,
)

logger = logging.getLogger(__name__)


class VideoRecorderProcessManager:
    def __init__(
        self,
        multi_frame_queue: multiprocessing.Queue,
    ):
        self._camera_configs: CameraConfigs = {}
        self._multi_frame_queue = multi_frame_queue

        self._process: Optional[VideoRecorderProcess] = None

    def start_recording(
        self,
        camera_configs: CameraConfigs,
        start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int],
        recording_folder_path: str,
    ):
        logger.debug(f"Starting recording with folder path: {recording_folder_path}...")
        self._process = VideoRecorderProcess(
            camera_configs=camera_configs,
            start_time_perf_counter_ns_to_unix_mapping=start_time_perf_counter_ns_to_unix_mapping,
            recording_folder_path=recording_folder_path,
            multi_frame_queue=self._multi_frame_queue,
        )
        self._process.start()

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._multi_frame_queue.put(None)
