import logging

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.opencv_apply_config import apply_camera_configuration
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import UpdateCamerasSettingsMessage, DeviceExtractedConfigMessage

logger = logging.getLogger(__name__)

def check_for_new_config(current_config: CameraConfig,
                         frame_rec_array: np.recarray,
                         cv2_video_capture: cv2.VideoCapture,
                         ipc: CameraGroupIPC,
                         self_status: CameraStatus,
                         update_camera_settings_subscription) -> tuple[np.recarray, CameraConfig]:
    if not update_camera_settings_subscription.empty():
        logger.debug(
            f"Camera {frame_rec_array.frame_metadata.camera_config.camera_id[0]} received update_camera_settings_subscription message")
        update_message = update_camera_settings_subscription.get()
        if not isinstance(update_message, UpdateCamerasSettingsMessage):
            raise RuntimeError(
                f"Expected UpdateCamerasSettingsMessage for camera {frame_rec_array.frame_metadata.camera_config.camera_id[0]}, "
                f"but received {type(update_message)}"
            )
        if frame_rec_array.frame_metadata.camera_config.camera_id[0] in update_message.requested_configs:
            self_status.updating.value = True
            new_config = update_message.requested_configs[frame_rec_array.frame_metadata.camera_config.camera_id[0]]
            extracted_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                          prior_config=CameraConfig.from_numpy_record_array(
                                                              frame_rec_array.frame_metadata.camera_config),
                                                          config=new_config, )
            frame_rec_array.frame_metadata.camera_config[0] = extracted_config.to_numpy_record_array()
            ipc.pubsub.topics[TopicTypes.EXTRACTED_CONFIG].publish(
                DeviceExtractedConfigMessage(extracted_config=extracted_config))
            self_status.updating.value = False
            current_config = extracted_config

    return frame_rec_array, current_config
