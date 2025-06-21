import logging
import multiprocessing

import cv2

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_apply_config import apply_camera_configuration
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator, CameraStatus
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.pubsub.pubsub_topics import SetShmMessage, DeviceExtractedConfigMessage, \
    UpdateCamerasSettingsMessage
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue, WorkerStrategy
from skellycam.utilities.wait_functions import wait_10us, wait_10ms

logger = logging.getLogger(__name__)


def opencv_camera_worker_method(camera_id: CameraIdString,
                                config: CameraConfig,
                                ipc: CameraGroupIPC,
                                update_camera_settings_subscription: TopicSubscriptionQueue,
                                shm_subscription: TopicSubscriptionQueue,
                                close_self_flag: multiprocessing.Value,
                                camera_worker_strategy: WorkerStrategy,
                                ):
    # Configure logging in the child process
    if camera_worker_strategy == WorkerStrategy.PROCESS:
        # Configure logging if multiprocessing (i.e. if there is a parent process)
        from skellycam.system.logging_configuration.configure_logging import configure_logging
        from skellycam import LOG_LEVEL
        configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication)
    logger.trace(f"Camera {camera_id} worker started")
    orchestrator: CameraOrchestrator = ipc.camera_orchestrator
    self_status: CameraStatus = orchestrator.camera_statuses[camera_id]
    self_status.running.value = True
    camera_shm: FramePayloadSharedMemoryRingBuffer | None = None

    def should_continue():
        return ipc.should_continue and not close_self_flag.value

    # Create cv2.VideoCapture object
    try:
        cv2_video_capture, config = create_cv2_video_capture(config)
    except Exception as e:
        logger.exception(f"Failed to create cv2.VideoCapture for camera {camera_id}: {e}")
        self_status.signal_error()
        close_self_flag.value = True
        ipc.kill_everything()
        raise RuntimeError(f"Could not create cv2.VideoCapture for camera {camera_id}") from e
    ipc.pubsub.topics[TopicTypes.EXTRACTED_CONFIG].publish(DeviceExtractedConfigMessage(extracted_config=config))
    self_status.connected.value = True

    logger.debug(f"Camera {config.camera_id} connected, awaiting shm message...")

    while camera_shm is None and should_continue():
        wait_10ms()
        if not shm_subscription.empty():
            shm_message: SetShmMessage = shm_subscription.get()
            if not isinstance(shm_message, SetShmMessage):
                raise RuntimeError(
                    f"Expected SetShmMessage for camera {camera_id}, but received {type(shm_message)}"
                )
            camera_shm_dto = shm_message.camera_group_shm_dto.camera_shm_dtos[camera_id]
            logger.debug(f"Creating camera shared memory for camera {camera_id}...")
            camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                                     read_only=False)

    # Ensure camera_group_shm is properly initialized before proceeding
    if camera_shm is None or not camera_shm.valid:
        raise RuntimeError("Failed to initialize camera_group_shm")
    logger.success(f"Camera {camera_id} ready!")

    while not ipc.all_ready and should_continue():
        wait_10ms()
    frame = FramePayload.create_initial(camera_config=config,
                                        timebase_mapping=ipc.timebase_mapping)

    try:
        logger.debug(f"Camera {config.camera_id} frame grab loop starting...")
        while should_continue():
            if self_status.should_pause.value or not config.use_this_camera:
                self_status.is_paused.value = True
                wait_10ms()
                continue
            self_status.is_paused.value = False
            frame = check_for_new_config(frame=frame,
                                         cv2_video_capture=cv2_video_capture,
                                         ipc=ipc,
                                         self_status=self_status,
                                         update_camera_settings_subscription=update_camera_settings_subscription)

            if not orchestrator.should_grab_by_id(camera_id=camera_id):
                wait_10us()
                continue

            self_status.grabbing_frame.value = True
            frame = opencv_get_frame(cap=cv2_video_capture, frame=frame)

            camera_shm.put_frame(frame_rec_array=frame.to_numpy_record_array(), overwrite=True)
            self_status.grabbing_frame.value = False
            frame.increment_frame_number()
            # Last camera to increment their frame count status triggers the next frame_grab
            self_status.frame_count.value = frame.frame_number
            frame.initialize()


    except Exception as e:
        self_status.signal_error()
        logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
        ipc.kill_everything()
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

        logger.debug(f"Camera {config.camera_index} process completed")


def check_for_new_config(frame: FramePayload,
                         cv2_video_capture: cv2.VideoCapture,
                         ipc: CameraGroupIPC,
                         self_status: CameraStatus,
                         update_camera_settings_subscription) -> FramePayload:
    if not update_camera_settings_subscription.empty():
        logger.debug(f"Camera {frame.camera_config.camera_id} received update_camera_settings_subscription message")
        self_status.updating.value = True
        update_message = update_camera_settings_subscription.get()
        if not isinstance(update_message, UpdateCamerasSettingsMessage):
            raise RuntimeError(
                f"Expected UpdateCamerasSettingsMessage for camera {frame.camera_config.camera_id}, "
                f"but received {type(update_message)}"
            )
        if not frame.camera_config.camera_id in update_message.requested_configs:
            raise RuntimeError(
                f"Camera {frame.camera_config.camera_id} not found in UpdateCamerasSettingsMessage: {update_message.requested_configs.keys()} "
            )
        new_config = update_message.requested_configs[frame.camera_config.camera_id]
        frame.camera_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                         prior_config=frame.camera_config,
                                                         config=new_config, )
        ipc.pubsub.topics[TopicTypes.EXTRACTED_CONFIG].publish(
            DeviceExtractedConfigMessage(extracted_config=frame.camera_config))
        self_status.updating.value = False
    return frame
