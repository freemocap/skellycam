import logging

import cv2
import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_helpers.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_helpers.create_initial_frame_recarray import create_initial_frame_rec_array
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import DeviceExtractedConfigMessage, SetShmMessage
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_10ms

logger = logging.getLogger(__name__)

def setup_opencv_camera_loop(camera_shm: CameraSharedMemoryRingBuffer | None,
                             config: CameraConfig,
                             ipc: CameraGroupIPC,
                             self_status: CameraStatus,
                             shm_subscription: TopicSubscriptionQueue) -> tuple[
    CameraSharedMemoryRingBuffer, CameraConfig, cv2.VideoCapture, np.recarray]:
    # Create cv2.VideoCapture object
    try:
        cv2_video_capture, config = create_cv2_video_capture(config)

        ipc.pubsub.topics[TopicTypes.EXTRACTED_CONFIG].publish(DeviceExtractedConfigMessage(extracted_config=config))
        self_status.connected.value = True
        logger.debug(f"Camera {config.camera_id} connected, awaiting shm message...")
        while camera_shm is None and ipc.should_continue:
            wait_10ms()
            if not shm_subscription.empty():
                shm_message: SetShmMessage = shm_subscription.get()
                if not isinstance(shm_message, SetShmMessage):
                    raise RuntimeError(
                        f"Expected SetShmMessage for camera {config.camera_id}, but received {type(shm_message)}"
                    )
                camera_shm_dto = shm_message.camera_group_shm_dto.camera_shm_dtos[config.camera_id]
                logger.debug(f"Creating camera shared memory for camera {config.camera_id}...")
                camera_shm = CameraSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                   read_only=False)
        # Ensure camera_group_shm is properly initialized before proceeding
        if camera_shm is None or not camera_shm.valid:
            raise RuntimeError("Failed to initialize camera_group_shm")
        logger.success(f"Camera {config.camera_id} ready!")
        while not ipc.all_ready_to_start and ipc.should_continue:
            wait_10ms()
        frame_rec_array = create_initial_frame_rec_array(config=config,
                                                         ipc=ipc)

    except Exception as e:
        logger.exception(f"Failed to create cv2.VideoCapture for camera {config.camera_id}: {e}")
        self_status.signal_error()
        ipc.kill_everything()
        raise RuntimeError(f"Could not create cv2.VideoCapture for camera {config.camera_id}") from e
    return camera_shm, config, cv2_video_capture, frame_rec_array
