import logging
import multiprocessing
import time

import cv2
import numpy as np

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
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import create_frame_dtype
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
    frame_rec_array = create_initial_frame_rec_array(config=config,
                                                     ipc=ipc)
    try:
        logger.debug(f"Camera {config.camera_id} frame grab loop starting...")
        while should_continue():
            if self_status.should_pause.value or not config.use_this_camera:
                self_status.is_paused.value = True
                wait_10ms()
                continue
            self_status.is_paused.value = False
            frame_rec_array = check_for_new_config(frame_rec_array=frame_rec_array,
                                                   cv2_video_capture=cv2_video_capture,
                                                   ipc=ipc,
                                                   self_status=self_status,
                                                   update_camera_settings_subscription=update_camera_settings_subscription)

            while not orchestrator.should_grab_by_id(camera_id=camera_id) and not self_status.should_pause.value and should_continue():
                wait_10us()
                continue

            self_status.grabbing_frame.value = True
            frame_rec_array = opencv_get_frame(cap=cv2_video_capture, frame_rec_array=frame_rec_array, )
            camera_shm.put_frame(frame_rec_array=frame_rec_array, overwrite=True)
            self_status.grabbing_frame.value = False
            frame_rec_array = initialize_frame_timestamps(frame_rec_array=frame_rec_array)
            # Last camera to increment their frame count status triggers the next frame_grab
            self_status.frame_count.value = frame_rec_array.frame_metadata.frame_number[0]



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


def create_initial_frame_rec_array(config: CameraConfig, ipc: CameraGroupIPC) -> np.recarray:
    # Create initial frame record array
    frame_dtype = create_frame_dtype(config)
    frame_rec_array = np.recarray(1, dtype=frame_dtype)
    # Initialize the frame metadata
    frame_rec_array.frame_metadata.camera_config[0] = config.to_numpy_record_array()
    frame_rec_array.frame_metadata.frame_number[0] = -1
    frame_rec_array.frame_metadata.timestamps.timebase_mapping[0] = ipc.timebase_mapping.to_numpy_record_array()
    # Initialize the image with zeros
    image_shape = (config.resolution.height, config.resolution.width, config.color_channels)
    frame_rec_array.image[0] = np.zeros(image_shape, dtype=np.uint8)+ config.camera_index
    return frame_rec_array


def check_for_new_config(frame_rec_array: np.recarray,
                         cv2_video_capture: cv2.VideoCapture,
                         ipc: CameraGroupIPC,
                         self_status: CameraStatus,
                         update_camera_settings_subscription) -> np.recarray:
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
                                                              frame_rec_array.frame_metadata.camera_config[0]),
                                                          config=new_config, )
            frame_rec_array.frame_metadata.camera_config[0] = extracted_config.to_numpy_record_array()
            ipc.pubsub.topics[TopicTypes.EXTRACTED_CONFIG].publish(
                DeviceExtractedConfigMessage(
                    extracted_config=CameraConfig.from_numpy_record_array(frame_rec_array.frame_metadata.camera_config[0])))
            self_status.updating.value = False

    return frame_rec_array


def initialize_frame_timestamps(frame_rec_array: np.recarray) -> np.recarray:
    """Initialize timestamps for a new frame"""

    # Reset all timestamps to 0
    frame_rec_array.frame_metadata.timestamps.pre_frame_grab_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_frame_grab_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_frame_retrieve_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_frame_retrieve_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_retrieve_from_camera_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_retrieve_from_camera_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_copy_to_multiframe_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.pre_retrieve_from_multiframe_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.post_retrieve_from_multiframe_shm_ns[0] = 0
    frame_rec_array.frame_metadata.timestamps.frame_initialized_ns[0] = time.perf_counter_ns()
    return frame_rec_array
