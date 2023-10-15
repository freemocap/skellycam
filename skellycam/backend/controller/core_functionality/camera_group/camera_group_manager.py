import threading
from typing import Dict, Optional

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group import CameraGroup
from skellycam.backend.controller.core_functionality.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.data_models.cameras.camera_config import CameraConfig


class CameraGroupManager:
    """
    creates a `camera_group` and then holds it in a looping thread.
    returns a two-way queue that will be used to send as-formatted-as-possble q_images to the frontend

    Also manages `video_recorders`  and will stuff images into them as they come in from the `camera_group`,
    provided that we are currently 'recording'  - otherwise, they'll just be slung at the front and
     then lost like tears in the rain.
    """

    def __init__(self):
        self._camera_group_thread = None

        self._camera_group = CameraGroup()
        self._camera_group_thread = threading.Thread(target=self._start_camera_group)
        self._camera_group_thread.start()

        self._cameras: Optional[Dict[str, CameraConfig]] = None

    def _start_camera_group(self):
        self._camera_group.start()


    def stop_camera_group(self):
        self._camera_group.stop()
        self._camera_group_thread.join()

    def update_configs(self, camera_configs):
        logger.debug(f"Updating camera configs to {camera_configs.keys()}")
        self._camera_group.update_configs(camera_configs=camera_configs)


    def get_video_recorders(self) -> Dict[str, VideoRecorder]:
        return self._video_recorders

    def _create_video_recorders(self, cameras: Dict[str, CameraConfig], video_save_directory: str = None):
        if video_save_directory is None:
            logger.debug(f"No video save directory provided, not creating video recorders")
            return

        logger.debug(f"Creating video recorders for cameras: {cameras.keys()} to save to {video_save_directory}")

        self._video_recorders = {camera_id: VideoRecorder(camera_config=camera_config,
                                                          video_save_path=video_save_directory,
                                                          ) for camera_id, camera_config in cameras.items()}
