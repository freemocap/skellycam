import logging
import multiprocessing

import cv2

from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_apply_config import apply_camera_configuration
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_connecton import CameraConnection
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import ExtractedConfigMessage, UpdateCameraConfigsMessage, \
    UpdateShmMessage, ExtractedConfigTopic
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBufferDTO, FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms, wait_10us, wait_10ms

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
    orchestrator = ipc.camera_orchestrator
    camera_connection: CameraConnection = orchestrator.connections[camera_id]
    camera_connection.status.running.value = True

    camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                             read_only=False)
    logger.debug(f"Camera {camera_id} shared memory re-created in CameraProcess for camera {camera_id}")

    def should_continue():
        return ipc.should_continue and not close_self_flag.value

    # Create cv2.VideoCapture object
    try:
        cv2_video_capture, extracted_config = create_cv2_video_capture(camera_connection.config)
        extracted_config_topic.publish(ExtractedConfigMessage(extracted_config=extracted_config))
    except Exception as e:
        logger.exception(f"Failed to create cv2.VideoCapture for camera {camera_id}: {e}")
        camera_connection.status.signal_error()
        close_self_flag.value = True
        ipc.kill_everything()
        raise RuntimeError(f"Could not create cv2.VideoCapture for camera {camera_id}") from e

    camera_connection.status.connected.value = True

    logger.success(f"Camera {extracted_config.camera_id} ready!")

    while not ipc.all_ready and should_continue():
        wait_1ms()

    try:
        logger.debug(f"Camera {extracted_config.camera_id} frame grab loop starting...")
        # Trigger listening loop
        while should_continue():
            frame_metadata = create_empty_frame_metadata(config=extracted_config,
                                                         frame_number=orchestrator.camera_frame_counts[camera_id] + 1)
            if ipc.should_pause_flag.value:
                camera_connection.status.is_paused.value = True
                wait_10ms()
                continue
            camera_connection.status.is_paused.value = False

            while should_continue() and not orchestrator.should_grab_by_id(camera_id=camera_id):
                wait_10us()

            camera_connection.status.grabbing_frame.value = True
            opencv_get_frame(cap=cv2_video_capture,
                             frame_metadata=frame_metadata,
                             camera_shared_memory=camera_shm,
                             )
            camera_connection.status.grabbing_frame.value = False

            # Check if the camera config has changed

            (camera_connection,
             camera_shm,
             extracted_config,
             orchestrator) = check_for_updates(camera_connection=camera_connection,
                                               camera_id=camera_id,
                                               camera_shm=camera_shm,
                                               cv2_video_capture=cv2_video_capture,
                                               extracted_config=extracted_config,
                                               extracted_config_topic=extracted_config_topic,
                                               orchestrator=orchestrator,
                                               update_configs_subscription=update_configs_subscription,
                                               update_shm_subscription=update_shm_subscription)

            # Last camera to increment their frame count triggers the next frame_grab signal
            camera_connection.status.frame_count.value += 1

    except Exception as e:
        camera_connection.status.signal_error()
        logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
        raise
    finally:
        logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
        camera_connection.status.signal_closing()
        close_self_flag.value = True
        ipc.should_continue = False
        if cv2_video_capture:
            cv2_video_capture.release()
        camera_shm.close()
        camera_connection.status.closed.value = True

        logger.debug(f"Camera {extracted_config.camera_index} process completed")


def check_for_updates(camera_connection: CameraConnection,
                      camera_id: CameraIdString,
                      camera_shm: FramePayloadSharedMemoryRingBuffer,
                      cv2_video_capture: cv2.VideoCapture,
                      extracted_config: FramePayloadSharedMemoryRingBufferDTO,
                      extracted_config_topic: ExtractedConfigTopic,
                      orchestrator: CameraOrchestrator,
                      update_configs_subscription: TopicSubscriptionQueue,
                      update_shm_subscription: TopicSubscriptionQueue):
    extracted_config = check_for_config_updates(camera_id=camera_id,
                                                cv2_video_capture=cv2_video_capture,
                                                extracted_config=extracted_config,
                                                extracted_config_topic=extracted_config_topic,
                                                update_configs_subscription=update_configs_subscription)
    camera_connection, camera_shm, orchestrator = check_for_shm_updates(camera_connection=camera_connection,
                                                                        camera_id=camera_id,
                                                                        camera_shm=camera_shm,
                                                                        extracted_config=extracted_config,
                                                                        orchestrator=orchestrator,
                                                                        update_shm_subscription=update_shm_subscription)
    return camera_connection, camera_shm, extracted_config, orchestrator


def check_for_shm_updates(camera_connection: CameraConnection,
                          camera_id: CameraIdString,
                          camera_shm: FramePayloadSharedMemoryRingBuffer,
                          extracted_config: FramePayloadSharedMemoryRingBufferDTO,
                          orchestrator: CameraOrchestrator,
                          update_shm_subscription: TopicSubscriptionQueue):
    if not update_shm_subscription.empty():
        update_shm_message = update_shm_subscription.get()
        if not isinstance(update_shm_message, UpdateShmMessage):
            raise TypeError(f"Received unexpected message type: {type(update_shm_message)}")
        camera_shm.close()
        camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(
            update_shm_message.group_shm_dto.camera_shm_dtos[camera_id],
            read_only=camera_shm.read_only)
        orchestrator = update_shm_message.orchestrator
        camera_connection = orchestrator.connections[camera_id]
        if not extracted_config == update_shm_message.group_shm_dto.camera_configs[camera_id]:
            raise ValueError(f"Camera {camera_id} config different than expected in UpdateShmMessage: "
                             f"{extracted_config} != {update_shm_message.group_shm_dto.camera_configs[camera_id]}")
    return camera_connection, camera_shm, orchestrator


def check_for_config_updates(camera_id, cv2_video_capture, extracted_config, extracted_config_topic,
                             update_configs_subscription):
    if not update_configs_subscription.empty():
        update_configs_message = update_configs_subscription.get()
        if not isinstance(update_configs_message, UpdateCameraConfigsMessage):
            raise TypeError(f"Received unexpected message type: {type(update_configs_message)}")
        if extracted_config != update_configs_message.old_configs[camera_id]:
            raise ValueError(f"Camera config changed outside of expected update flow! \nExpected: {extracted_config}, \nReceived: {update_configs_message.old_configs[camera_id]}")

        new_config = update_configs_message.new_configs[camera_id]
        extracted_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                      prior_config=extracted_config,
                                                      config=new_config)
        extracted_config_topic.publish(ExtractedConfigMessage(extracted_config=extracted_config))

        logger.debug(f"Received updated config for camera {camera_id}: {extracted_config}")
    return extracted_config
