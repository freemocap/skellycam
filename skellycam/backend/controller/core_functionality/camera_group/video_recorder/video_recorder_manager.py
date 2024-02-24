import logging
import multiprocessing
import time
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
    ):
        self._timestamp_manager: Optional[TimestampLoggerManager] = None
        self._video_recorders: Dict[CameraId, VideoRecorder] = {}
        self._multi_frame_number = 0
        self._camera_configs = camera_configs

        self._multi_frame_queue = multi_frame_queue

        self._is_recording = False
        self._should_continue = True

        self.process = Process(
            target=self.save_frames_process, args=(self._multi_frame_queue,)
        )

    @property
    def has_frames_to_save(self):
        return any(
            [
                video_recorder.has_frames_to_save
                for video_recorder in self._video_recorders.values()
            ]
        )

    @property
    def finished(self):
        all_video_recorders_finished = all(
            [
                video_recorder.finished
                for video_recorder in self._video_recorders.values()
            ]
        )
        timestamp_manager_finished = self._timestamp_manager.finished
        return all_video_recorders_finished and timestamp_manager_finished

    def save_frames_process(self, frame_queue: multiprocessing.Queue):
        logger.debug("Starting save frames process...")
        while self._should_continue:
            multi_frame_payload = (
                frame_queue.get()
            )  # This will block until an item is available
            self._handle_multi_frame_payload(multi_frame_payload)

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
        self.process.start()

    def stop_recording(self):
        logger.debug(f"Stopping recording...")
        self._is_recording = False
        self.finish_and_close()
        self._should_continue = False

    def _handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        self._multi_frame_number += 1
        logger.trace(f"Handling multi frame payload #{self._multi_frame_number}...")
        for camera_id, frame_payload in multi_frame_payload.frames.items():
            self._video_recorders[CameraId(camera_id)].append_frame_payload_to_list(
                frame_payload=frame_payload
            )
        self._timestamp_manager.handle_multi_frame_payload(
            multi_frame_payload=multi_frame_payload,
            multi_frame_number=self._multi_frame_number,
        )

        # TODO - refactor to skip this weird double step method of saving a frame
        self.one_frame_to_disk()

    def one_frame_to_disk(self):
        logger.trace(f"Saving one multi_frame to disk...")
        for video_recorder in self._video_recorders.values():
            video_recorder.one_frame_to_disk()

    def finish_and_close(self):
        for camera_id, video_recorder in self._video_recorders.items():
            logger.debug(
                f"Finishing and closing video recorder for camera {camera_id}..."
            )
            video_recorder.finish_and_close()
        self._timestamp_manager.close()

        while not self.finished:
            time.sleep(0.1)

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
                video_save_path=self._make_video_file_path(
                    camera_id=camera_id,
                    recording_folder_path=recording_folder_path,
                    writer_fourcc=camera_config.writer_fourcc,
                ),
            )
            for camera_id, camera_config in self._camera_configs.items()
        }

    def _make_video_file_path(
        self, camera_id: CameraId, recording_folder_path: str, writer_fourcc: str
    ):
        video_file_extension = fourcc_to_file_extension(writer_fourcc)

        Path(recording_folder_path).mkdir(parents=True, exist_ok=True)
        file_name = f"{Path(recording_folder_path).stem}_camera_{camera_id}.{video_file_extension}"
        logger.debug(
            f"Saving video from camera {camera_id} to: {Path(recording_folder_path) / file_name}..."
        )
        return str(Path(recording_folder_path) / file_name)


def fourcc_to_file_extension(writer_fourcc: str) -> str:
    if writer_fourcc == "MJPG" or writer_fourcc == "XVID":
        video_format = "avi"
    elif writer_fourcc == "H264":
        video_format = "mp4"
    else:
        logger.warning(f"Unknown video format {writer_fourcc} - defaulting to avi")
        video_format = "avi"
    return video_format
