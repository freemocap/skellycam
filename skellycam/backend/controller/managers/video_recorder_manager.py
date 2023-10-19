from pathlib import Path
from typing import Dict

from skellycam.backend.controller.core_functionality.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.camera_id import CameraId
from skellycam.models.cameras.frames.frame_payload import FramePayload


class VideoRecorderManager:
    """
    Creates a dictionary of `video_recorders` and then awaits new_images to be sent to it.
    When it receives a new image, it will stuff it into the appropriate `video_recorder`

    Parameters:
    -----------
    cameras: Dict[CameraId, CameraConfig]
        A dictionary of `CameraConfig` objects, keyed by camera_id
    video_save_directory: str
        The directory to save videos to, videos will be saved to this directory as `[Path(video_save_directory)/Path(video_save_directory).stem]_camera_[camera_id].mp4`

    Methods:
    --------
    handle_new_images(new_images: Dict[str, FramePayload]):
        Takes in a dictionary of `FramePayload` objects, keyed by camera_id
        Stuffs each `FramePayload` into the appropriate `video_recorder` object
    """

    def __init__(self,
                 cameras: Dict[CameraId, CameraConfig],
                 video_save_directory: str = None):
        self._cameras = cameras
        self._video_save_directory = video_save_directory
        self._video_recorders = {camera_id: VideoRecorder(camera_config=camera_config,
                                                          video_save_path=self._make_video_save_path(
                                                              camera_id=camera_id)
                                                          ) for camera_id, camera_config in cameras.items()}

    def handle_new_images(self, new_images: Dict[str, FramePayload]):
        for camera_id, frame_payload in new_images.items():
            self._video_recorders[camera_id].append_frame_payload_to_list(frame_payload=frame_payload)

    def _make_video_save_path(self, camera_id: CameraId):
        """
        So, like,  if self._video_save_directory is "/home/user/videos" and camera_id is "0", then this will return "/home/user/recording_name/recording_name_camera_0.mp4"
        This is a bit redundant, but it will save us from having a thousand `camera0.mp4` videos floating around in our lives
        """
        f = 9
        file_name = f"{Path(self._video_save_directory).stem}_camera_{camera_id}.mp4"
        return str(Path(self._video_save_directory) / file_name)
