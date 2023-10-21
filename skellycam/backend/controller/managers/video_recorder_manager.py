from pathlib import Path
from typing import Dict

from skellycam.backend.controller.core_functionality.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import MultiFramePayload
from skellycam.system.environment.default_paths import get_default_session_folder_path


class VideoRecorderManager:

    def __init__(self,
                 cameras: Dict[CameraId, CameraConfig],
                 video_save_directory: str = get_default_session_folder_path(create_folder=False)):
        self._cameras = cameras
        self._video_save_directory = video_save_directory
        self._video_recorders: Dict[CameraId, VideoRecorder] = {camera_id: VideoRecorder(camera_config=camera_config,
                                                                                         video_save_path=self._make_video_file_path(
                                                                                             camera_id=camera_id)
                                                                                         ) for camera_id, camera_config
                                                                in cameras.items()}

    def handle_multi_frame_payload(self, multi_frame_payload: MultiFramePayload):
        for camera_id, frame_payload in multi_frame_payload.frames.items():
            self._video_recorders[camera_id].append_frame_payload_to_list(frame_payload=frame_payload)

    def one_frame_to_disk(self):
        for video_recorder in self._video_recorders.values():
            video_recorder.one_frame_to_disk()

    def finish_and_close(self):
        for camera_id, video_recorder in self._video_recorders.items():
            video_recorder.finish_and_close()

    def _make_video_file_path(self, camera_id: CameraId, video_format: str = "mp4"):
        """
        So, like,  if self._video_save_directory is "/home/user/videos" and camera_id is "0", then this will return "/home/user/recording_name/recording_name_camera_0.mp4"
        This is a bit redundant, but it will save us from having a thousand `camera0.mp4` videos floating around in our lives
        """
        f = 9
        file_name = f"{Path(self._video_save_directory).stem}_camera_{camera_id}.{video_format}"
        return str(Path(self._video_save_directory) / file_name)
