import logging
from typing import Tuple, Optional
from multiprocessing import Queue
from multiprocessing.synchronize import Event as MultiprocessingEvent

from skellycam.core.cameras.config.camera_config import CameraConfigs
from skellycam.core.consumers.recorder.video_recorder_process import (
    VideoRecorderProcess,
)

logger = logging.getLogger(__name__)


class VideoRecorderProcessManager:
    def __init__(
        self,
        recording_queue: Queue,  # TODO: potentially, we make this optional and just bypass the start process if no queue is provided, covering the case where we just don't record?
        recording_event: MultiprocessingEvent,
    ):
        self.recording_queue = recording_queue
        self.recording_event = recording_event

        self._camera_configs: CameraConfigs = {}
        self._process: Optional[VideoRecorderProcess] = None

    def await_recording(
        self,
        camera_configs: CameraConfigs,
        start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int],
        recording_folder_path: str,
    ):
        """
        We want a controller-level function that allow sus to only start recording once the the recording_event is set
        This would probably be async, so we can loop while waiting for the event without blocking the main process
        
        We need to decide if it makes sense to initialize the process here and only start it once the event is set,
        or if we want to wait for the event to initialize and start
        """
        pass

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
            multi_frame_queue=self.recording_queue,
            recording_event=self.recording_event,
        )
        self.recording_event.set()
        self._process.start()

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self.recording_queue.put(None)
        self.recording_event.clear()  # TODO: the put(None) may be redundant now that we have a recording event

        self._process.join() if self._process else None
