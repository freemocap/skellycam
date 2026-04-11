import logging

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.check_for_new_config import check_for_new_config
from skellycam.core.camera.opencv.opencv_helpers.handle_recording_updates import check_for_new_recording_info
from skellycam.core.camera_group.camera_group_helpers.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_group_helpers.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_group_helpers.camera_status import CameraStatus
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.types.type_overloads import TopicSubscriptionQueue

logger = logging.getLogger(__name__)


def camera_loop_update_checks(config: CameraConfig,
                              cv2_video_capture: cv2.VideoCapture,
                              frame_rec_array: np.recarray,
                              ipc: CameraGroupIPC,
                              orchestrator: CameraOrchestrator,
                              recording_info_subscription: TopicSubscriptionQueue,
                              self_status: CameraStatus,
                              update_camera_settings_subscription: TopicSubscriptionQueue,
                              video_recorder: VideoRecorder | None,
                                framerate: float | None = None
                              ) -> tuple[
    CameraConfig, np.recarray, VideoRecorder | None, CameraStatus]:
    video_recorder = check_for_new_recording_info(config=config,
                                                  ipc=ipc,
                                                  orchestrator=orchestrator,
                                                  recording_info_subscription=recording_info_subscription,
                                                  self_status=self_status,
                                                  video_recorder=video_recorder,
                                                  framerate=framerate)

    frame_rec_array, config = check_for_new_config(current_config=config,
                                                   frame_rec_array=frame_rec_array,
                                                   cv2_video_capture=cv2_video_capture,
                                                   ipc=ipc,
                                                   self_status=self_status,
                                                   update_camera_settings_subscription=update_camera_settings_subscription)

    self_status = check_camera_should_pause(config=config,
                                            ipc=ipc,
                                            self_status=self_status)

    return config, frame_rec_array, video_recorder, self_status


def check_camera_should_pause(config: CameraConfig,
                              ipc: CameraGroupIPC,
                              self_status: CameraStatus) -> CameraStatus:
    if self_status.should_pause.value:
        if not self_status.is_paused.value:
            logger.trace(f"Pausing camera {config.camera_id}...")
            self_status.is_paused.value = True
    else:
        if self_status.is_paused.value:
            logger.trace(f"Resuming camera {config.camera_id}...")
            self_status.is_paused.value = False
    return self_status
