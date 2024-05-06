import logging
import multiprocessing
from multiprocessing import Process
from pathlib import Path
from typing import Dict, Tuple

from setproctitle import setproctitle

from skellycam.core.cameras.config.camera_config import CameraConfig
from skellycam.core.device_detection.camera_id import CameraId
from skellycam.core.frames.multi_frame_payload import MultiFramePayload
from skellycam.core.timestamps.timestamp_logger_manager import (
    TimestampLoggerManager,
)
from skellycam.core.video_recorder.video_recorder import (
    VideoRecorder,
)

logger = logging.getLogger(__name__)


class VideoRecorderProcess(Process):
    def __init__(
        self,
        camera_configs: Dict[CameraId, CameraConfig],
        start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int],
        recording_folder_path: str,
        multi_frame_queue: multiprocessing.Queue,
    ):
        super().__init__()
        self._multi_frame_number = 0
        self._multi_frame_queue = multi_frame_queue
        self._camera_configs = camera_configs
        self._start_time_perf_counter_ns_to_unix_mapping = (
            start_time_perf_counter_ns_to_unix_mapping
        )
        self._recording_folder_path = recording_folder_path
        Path(self._recording_folder_path).mkdir(parents=True, exist_ok=True)

        self._initialize_timestamp_manager()
        self._initialize_video_recorders(recording_folder_path=recording_folder_path)

    def run(self):
        logger.debug("Starting save frames process...")
        setproctitle("Video Recorder Manager Process")
        while True:
            multi_frame_payload = self._multi_frame_queue.get()

            if multi_frame_payload is None:
                logger.debug(
                    "Received None from multi frame queue, exiting save frames process..."
                )
                break
            self._handle_multi_frame_payload(multi_frame_payload)

        logger.debug("Exiting save frames process...")
        self._timestamp_manager.close()
        self._close_video_recorders()

        logger.debug("Exiting save frames process...")

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

    def _initialize_timestamp_manager(
        self,
    ):
        logger.debug(
            f"Initializing timestamp manager with recording folder path: {self._recording_folder_path}"
        )
        self._timestamp_manager = TimestampLoggerManager(
            video_save_directory=str(self._recording_folder_path),
            camera_configs=self._camera_configs,
        )
        self._timestamp_manager.set_time_mapping(
            self._start_time_perf_counter_ns_to_unix_mapping
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

    def _close_video_recorders(self):
        logger.debug("Closing video recorders...")
        for video_recorder in self._video_recorders.values():
            video_recorder.close()


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
