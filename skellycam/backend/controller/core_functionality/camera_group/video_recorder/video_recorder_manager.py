import time
from pathlib import Path
from typing import Dict, Tuple

from skellycam.backend.controller.core_functionality.camera_group.video_recorder.timestamps.timestamp_logger_manager import \
    TimestampLoggerManager
from skellycam.backend.controller.core_functionality.camera_group.video_recorder.video_recorder import VideoRecorder
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.system.environment.default_paths import get_default_recording_folder_path


class VideoRecorderManager:

    def __init__(self,
                 camera_configs: Dict[CameraId, CameraConfig],
                 video_save_directory: str = get_default_recording_folder_path(create_folder=False)):
        self._multi_frame_number = 0
        self._camera_configs = camera_configs
        self._video_save_directory = video_save_directory
        self._timestamp_manager = TimestampLoggerManager(video_save_directory=self._video_save_directory,
                                                         camera_configs=camera_configs)
        self._video_recorders: Dict[CameraId, VideoRecorder] = {camera_id: VideoRecorder(camera_config=camera_config,
                                                                                         video_save_path=self._make_video_file_path(
                                                                                             camera_id=camera_id)
                                                                                         ) for camera_id, camera_config
                                                                in camera_configs.items()}
        self._is_recording = False

    @property
    def has_frames_to_save(self):
        return any([video_recorder.has_frames_to_save for video_recorder in self._video_recorders.values()])

    @property
    def finished(self):
        all_video_recorders_finished = all([video_recorder.finished for video_recorder in
                                            self._video_recorders.values()])
        timestamp_manager_finished = self._timestamp_manager.finished
        return all_video_recorders_finished and timestamp_manager_finished

    def start_recording(self, start_time_perf_counter_ns_to_unix_mapping: Tuple[int, int]):

        self._timestamp_manager.set_time_mapping(start_time_perf_counter_ns_to_unix_mapping)
        self._is_recording = True

    def stop_recording(self):
        self._is_recording = False

    def handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        self._multi_frame_number += 1
        for camera_id, frame_payload in multi_frame_payload.frames.items():
            self._video_recorders[camera_id].append_frame_payload_to_list(frame_payload=frame_payload)
        self._timestamp_manager.handle_multi_frame_payload(multi_frame_payload=multi_frame_payload,
                                                           multi_frame_number=self._multi_frame_number)

    def one_frame_to_disk(self):
        for video_recorder in self._video_recorders.values():
            video_recorder.one_frame_to_disk()

    def finish_and_close(self):
        for camera_id, video_recorder in self._video_recorders.items():
            video_recorder.finish_and_close()
        self._timestamp_manager.close()

        while not self.finished:
            time.sleep(0.001)


    def _make_video_file_path(self, camera_id: CameraId, video_format: str = "avi"):
        """
        So, like,  if self._video_save_directory is "/home/user/videos" and camera_id is "0", then this will return "/home/user/[recording_name]/[recording_name]_camera_0.mp4"
        This is a bit redundant, but it will save us from having a thousand `camera0.mp4` videos floating around in our lives
        """
        file_name = f"{Path(self._video_save_directory).stem}_camera_{camera_id}.{video_format}"
        return str(Path(self._video_save_directory) / file_name)
