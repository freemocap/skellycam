import asyncio
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
from skellycam.backend.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.system.default_paths import create_default_recording_folder_path

import logging

logger = logging.getLogger(__name__)


class VideoRecorderManager:
    def __init__(
        self,
        camera_configs: Dict[CameraId, CameraConfig],
    ):
        self._timestamp_manager: Optional[TimestampLoggerManager] = None
        self._video_recorders: Dict[CameraId, VideoRecorder] = {}
        self._multi_frame_number = 0
        self._camera_configs = camera_configs

        self._is_recording = False

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
            camera_id: VideoRecorder(
                camera_config=camera_config,
                video_save_path=self._make_video_file_path(
                    camera_id=camera_id,
                    recording_folder_path=recording_folder_path,
                ),
            )
            for camera_id, camera_config in self._camera_configs.items()
        }

    def stop_recording(self):
        self._is_recording = False

    def handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        self._multi_frame_number += 1
        for camera_id, frame_payload in multi_frame_payload.frames.items():
            self._video_recorders[camera_id].append_frame_payload_to_list(
                frame_payload=frame_payload
            )
        self._timestamp_manager.handle_multi_frame_payload(
            multi_frame_payload=multi_frame_payload,
            multi_frame_number=self._multi_frame_number,
        )

    def one_frame_to_disk(self):
        for video_recorder in self._video_recorders.values():
            video_recorder.one_frame_to_disk()

    async def finish_and_close(self):
        for camera_id, video_recorder in self._video_recorders.items():
            video_recorder.finish_and_close()
        self._timestamp_manager.close()

        while not self.finished:
            await asyncio.sleep(0.001)

    def _make_video_file_path(
        self, camera_id: CameraId, recording_folder_path: str, video_format: str = "mp4"
    ):
        Path(recording_folder_path).mkdir(parents=True, exist_ok=True)
        file_name = (
            f"{Path(recording_folder_path).stem}_camera_{camera_id}.{video_format}"
        )
        return str(Path(recording_folder_path) / file_name)
