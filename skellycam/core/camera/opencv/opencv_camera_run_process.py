import logging
import multiprocessing
from copy import deepcopy

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_apply_config import apply_camera_configuration
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.status_models import CameraStatus
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import ExtractedConfigMessage, UpdateShmMessage, ExtractedConfigTopic
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBufferDTO, FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_10us, wait_10ms, wait_100ms

logger = logging.getLogger(__name__)


def opencv_camera_run_process(camera_id: CameraIdString,
                              ipc: CameraGroupIPC,
                              camera_shm_dto: FramePayloadSharedMemoryRingBufferDTO,
                              extracted_config_topic: ExtractedConfigTopic,
                              update_configs_subscription: TopicSubscriptionQueue,
                              update_shm_subscription: TopicSubscriptionQueue,
                              close_self_flag: multiprocessing.Value,
                              ):
    # Configure logging in the child process
    from skellycam.system.logging_configuration.configure_logging import configure_logging
    from skellycam import LOG_LEVEL
    configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication, )
    logger.trace(f"Camera {camera_id} process started")
    current_config = deepcopy(ipc.camera_configs[camera_id])
    orchestrator = ipc.camera_orchestrator
    self_status: CameraStatus = orchestrator.camera_statuses[camera_id]
    self_status.running.value = True

    def should_continue():
        return ipc.should_continue and not close_self_flag.value

    # Create cv2.VideoCapture object
    try:
        cv2_video_capture, current_config = create_cv2_video_capture(current_config)
        extracted_config_topic.publish(ExtractedConfigMessage(extracted_config=current_config))
    except Exception as e:
        logger.exception(f"Failed to create cv2.VideoCapture for camera {camera_id}: {e}")
        self_status.signal_error()
        close_self_flag.value = True
        ipc.kill_everything()
        raise RuntimeError(f"Could not create cv2.VideoCapture for camera {camera_id}") from e

    self_status.connected.value = True

    logger.debug(f"Camera {current_config.camera_id} connected, re-creating shared memory buffer...")
    # Check if shm updates available before creating the shared memory buffer
    wait_100ms()
    if not update_shm_subscription.empty():
        update_shm_message = update_shm_subscription.get()
        if not isinstance(update_shm_message, UpdateShmMessage):
            raise TypeError(f"Received unexpected message type: {type(update_shm_message)}")
        camera_shm_dto = update_shm_message.group_shm_dto.camera_shm_dtos[camera_id]
        orchestrator = update_shm_message.orchestrator

    camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                             read_only=False)
    logger.success(f"Camera {camera_id} ready!")

    while not ipc.all_ready and should_continue():
        wait_10ms()

    try:
        logger.debug(f"Camera {current_config.camera_id} frame grab loop starting...")
        while should_continue():
            frame_metadata = create_empty_frame_metadata(config=current_config,
                                                         frame_number=orchestrator.camera_frame_counts[camera_id] + 1)
            if ipc.should_pause_flag.value or not current_config.use_this_camera:
                self_status.is_paused.value = True
                wait_10ms()
                continue

            self_status.is_paused.value = False
            current_config = check_for_config_updates(camera_id=camera_id,
                                                      cv2_video_capture=cv2_video_capture,
                                                      current_config=current_config,
                                                      ipc=ipc)

            self_status, camera_shm, orchestrator = check_for_shm_updates(self_status=self_status,
                                                                          camera_id=camera_id,
                                                                          camera_shm=camera_shm,
                                                                          orchestrator=orchestrator,
                                                                          update_shm_subscription=update_shm_subscription
                                                                          )
            if not orchestrator.should_grab_by_id(camera_id=camera_id):
                wait_10us()
                continue

            self_status.grabbing_frame.value = True
            opencv_get_frame(cap=cv2_video_capture,
                             frame_metadata=frame_metadata,
                             camera_shared_memory=camera_shm,
                             )
            self_status.grabbing_frame.value = False
            # Last camera to increment their frame count triggers the next frame_grab signal
            self_status.frame_count.value += 1

    except Exception as e:
        self_status.signal_error()
        logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
        raise
    finally:
        logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
        self_status.signal_closing()
        close_self_flag.value = True
        ipc.should_continue = False
        if cv2_video_capture:
            cv2_video_capture.release()
        camera_shm.close()
        self_status.closed.value = True

        logger.debug(f"Camera {current_config.camera_index} process completed")


def check_for_config_updates(camera_id: CameraIdString,
                             ipc: CameraGroupIPC,
                             cv2_video_capture: cv2.VideoCapture,
                             current_config: CameraConfig):
    if not current_config == ipc.camera_configs[camera_id]:
        current_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                    prior_config=current_config,
                                                    config=deepcopy(ipc.camera_configs[camera_id]))
        ipc.camera_configs[camera_id] = deepcopy(current_config)

    return current_config


def check_for_shm_updates(self_status: CameraStatus,
                          camera_id: CameraIdString,
                          camera_shm: FramePayloadSharedMemoryRingBuffer,
                          orchestrator: CameraOrchestrator,
                          update_shm_subscription: TopicSubscriptionQueue) -> tuple[
    CameraStatus, FramePayloadSharedMemoryRingBuffer, CameraOrchestrator]:
    if not update_shm_subscription.empty():
        update_shm_message = update_shm_subscription.get()
        if not isinstance(update_shm_message, UpdateShmMessage):
            raise TypeError(f"Received unexpected message type: {type(update_shm_message)}")
        camera_shm.close()
        camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(
            update_shm_message.group_shm_dto.camera_shm_dtos[camera_id],
            read_only=camera_shm.read_only)
        orchestrator = update_shm_message.orchestrator
        self_status = orchestrator.camera_statuses[camera_id]
    return self_status, camera_shm, orchestrator
