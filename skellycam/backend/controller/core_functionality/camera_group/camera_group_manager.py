import multiprocessing
import threading
import time
from typing import Dict, Optional, List

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group import CameraGroup
from skellycam.backend.controller.core_functionality.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.models.cameras.camera_config import CameraConfig
from skellycam.models.cameras.frame_models.frame_payload import FramePayload


class CameraGroupManager:
    """
    creates a `camera_group` and then holds it in a looping thread.
    returns a two-way queue that will be used to send as-formatted-as-possble q_images to the frontend

    Also manages `video_recorders`  and will stuff images into them as they come in from the `camera_group`,
    provided that we are currently 'recording'  - otherwise, they'll just be slung at the front and
     then lost like tears in the rain.
    """

    def __init__(self,
                 camera_configs: Dict[str, CameraConfig],
                 frontend_frame_queue: multiprocessing.Queue,) -> None:
        self.frontend_frame_queue = frontend_frame_queue
        self._camera_group: Optional[CameraGroup] = None
        self._camera_group_thread: Optional[threading.Thread] = None

        self._camera_configs = camera_configs
        self.incoming_frames_by_camera: Dict[str, List[FramePayload]] = {camera_id: [] for camera_id in
                                                                         camera_configs.keys()}
        self._create_camera_group()

    def _create_video_recorders(self, cameras: Dict[str, CameraConfig], video_save_directory: str = None):
        if video_save_directory is None:
            logger.debug(f"No video save directory provided, not creating video recorders")
            return

        logger.debug(f"Creating video recorders for cameras: {cameras.keys()} to save to {video_save_directory}")

        self._video_recorders = {camera_id: VideoRecorder(camera_config=camera_config,
                                                          video_save_path=video_save_directory,
                                                          ) for camera_id, camera_config in cameras.items()}

    def _create_camera_group(self):
        self._camera_group = CameraGroup(camera_configs=self._camera_configs,
                                         frontend_frame_queue=self.frontend_frame_queue,)
        self._camera_group_thread = threading.Thread(target=self._run_camera_group_loop, )

    def _run_camera_group_loop(self):
        self._camera_group.start()
        while not self._camera_group.exit_event.is_set():
            time.sleep(0.001)
            new_frames = self._camera_group.new_frames()
            if new_frames:
                for frame in new_frames:
                    self.incoming_frames_by_camera[frame.camera_id].append(frame)
                print(
                    f"Frame count by camera: {[f'Camera {camera_id}, Frame count: {len(frames)}' for camera_id, frames in self.incoming_frames_by_camera.items()]}")

    def start(self):
        logger.debug(f"Starting camera group thread...")
        self._camera_group_thread.start()

    def get_video_recorders(self) -> Dict[str, VideoRecorder]:
        return self._video_recorders

    def stop_camera_group(self):
        logger.debug(f"Stopping camera group thread...")
        self._camera_group.close()
        self._camera_group_thread.join()

    def update_configs(self, camera_configs: Dict[str, CameraConfig]):
        logger.debug(f"Updating camera configs to {camera_configs.keys()}")
        self._camera_group.update_configs(camera_configs=camera_configs)
