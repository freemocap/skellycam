import logging
import multiprocessing
from multiprocessing import Process
from pathlib import Path
from typing import Dict, Tuple, Optional

from skellycam.backend.controller.core_functionality.camera_group.video_recorder.timestamps.timestamp_logger_manager import (
    TimestampLoggerManager,
)
from skellycam.backend.controller.core_functionality.camera_group.video_recorder.video_recorder import (
    VideoRecorder,
)
from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.models.cameras.frames.multi_frame_payload import (
    MultiFramePayload,
)

logger = logging.getLogger(__name__)


class VideoRecorderManager:
    def __init__(
        self,
        camera_configs: Dict[CameraId, CameraConfig],
        multi_frame_queue: multiprocessing.Queue,
        exit_event: multiprocessing.Event,
    ):
        self._timestamp_manager: Optional[TimestampLoggerManager] = None
        self._video_recorders: Dict[CameraId, VideoRecorder] = {}
        self._multi_frame_number = 0
        self._camera_configs = camera_configs

        self._multi_frame_queue = multi_frame_queue

        self._is_recording = False

        self.process = Process(
            target=self._save_frames_process, args=(self._multi_frame_queue, exit_event)
        )
        self.process.start()

    def _save_frames_process(
        self, frame_queue: multiprocessing.Queue, exit_event: multiprocessing.Event
    ):
        logger.debug("Starting save frames process...")
        while not exit_event.is_set():
            multi_frame_payload = (
                frame_queue.get()
            )  # This will block until an item is available
            self._handle_multi_frame_payload(multi_frame_payload)

        if exit_event.is_set():
            logger.debug("Exiting save frames process due to exit event...")
        else:
            logger.debug("Exiting save frames process due to should_continue flag...")

        for camera_id, video_recorder in self._video_recorders.items():
            logger.debug(f"Closing video recorder for camera {camera_id}...")
            video_recorder.close()

    def start_recording(
        self,
        start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int],
        recording_folder_path: str,
    ):
        self._initialize_timestamp_manager(
            start_time_perf_counter_ns_to_unix_mapping=start_time_perf_counter_ns_to_unix_mapping,
            recording_folder_path=recording_folder_path,
        )
        self._initialize_video_recorders(
            recording_folder_path=recording_folder_path,
        )

        self._is_recording = True

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._is_recording = False
        self.close()

    def _handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        self._multi_frame_number += 1
        logger.trace(f"Handling multi frame payload #{self._multi_frame_number}...")
        self._save_frame_to_disk(multi_frame_payload)

        self._timestamp_manager.handle_multi_frame_payload(
            multi_frame_payload=multi_frame_payload,
            multi_frame_number=self._multi_frame_number,
        )

    def _save_frame_to_disk(self, multi_frame_payload: MultiFramePayload):
        """
        Save each frame from this multi-frame payload to disk.
        """
        for camera_id, video_recorder in self._video_recorders.items():
            video_recorder.save_frame_to_disk(multi_frame_payload.frames[camera_id])

    def close(self):
        for camera_id, video_recorder in self._video_recorders.items():
            logger.debug(
                f"Finishing and closing video recorder for camera {camera_id}..."
            )
            video_recorder.close()
        self._timestamp_manager.close()

    def _initialize_timestamp_manager(
        self,
        recording_folder_path: str,
        start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int],
    ):
        logger.debug(
            f"Initializing timestamp manager with recording folder path: {recording_folder_path}"
        )
        self._timestamp_manager = TimestampLoggerManager(
            video_save_directory=recording_folder_path,
            camera_configs=self._camera_configs,
        )
        self._timestamp_manager.set_time_mapping(
            start_time_perf_counter_ns_to_unix_mapping
        )

    def _initialize_video_recorders(
        self,
        recording_folder_path: str,
    ):
        logger.debug(
            f"Initializing video recorders with recording folder path: {recording_folder_path}"
        )

        self._video_recorders: Dict[CameraId, VideoRecorder] = {
            CameraId(camera_id): VideoRecorder(
                camera_config=camera_config,
                video_save_path=make_video_file_path(
                    camera_id=camera_id,
                    recording_folder_path=recording_folder_path,
                    writer_fourcc=camera_config.writer_fourcc,
                ),
            )
            for camera_id, camera_config in self._camera_configs.items()
        }


def make_video_file_path(
    camera_id: CameraId, recording_folder_path: str, writer_fourcc: str
):
    video_file_extension = fourcc_to_file_extension(writer_fourcc)

    Path(recording_folder_path).mkdir(parents=True, exist_ok=True)
    file_name = (
        f"{Path(recording_folder_path).stem}_camera_{camera_id}.{video_file_extension}"
    )
    logger.debug(
        f"Saving video from camera {camera_id} to: {Path(recording_folder_path) / file_name}..."
    )
    return str(Path(recording_folder_path) / file_name)


def fourcc_to_file_extension(writer_fourcc: str) -> str:
    if writer_fourcc == "MJPG" or writer_fourcc == "XVID":
        video_format = "avi"
    elif writer_fourcc == "H264" or writer_fourcc == "MP4V":
        video_format = "mp4"
    else:
        logger.error(f"Unknown video format {writer_fourcc}")
        raise ValueError(f"Unknown video format {writer_fourcc}")

    return video_format
