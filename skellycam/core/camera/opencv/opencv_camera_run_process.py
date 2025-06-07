import logging
import multiprocessing
from copy import deepcopy

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_apply_config import apply_camera_configuration
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_connecton import CameraConnection
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.ipc.pubsub.pubsub_manager import TopicSubscriptionQueue, TopicPublicationQueue
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBufferDTO, FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_1ms, wait_10us

logger = logging.getLogger(__name__)


def opencv_camera_run_process(camera_id: CameraIdString,
                              ipc: CameraGroupIPC,
                              config_update_subscription:TopicSubscriptionQueue,
                              extracted_configs_publication: TopicPublicationQueue,
                              camera_shm_dto: FramePayloadSharedMemoryRingBufferDTO,
                              close_self_flag: multiprocessing.Value,
                              ws_queue: multiprocessing.Queue,
                              ):
    # Configure logging in the child process
    from skellycam.system.logging_configuration.configure_logging import configure_logging
    from skellycam import LOG_LEVEL
    configure_logging(LOG_LEVEL, ws_queue=ws_queue)
    orchestrator = ipc.camera_orchestrator
    camera_connection:CameraConnection  = orchestrator.connections[camera_id]
    camera_connection.status.running.value = True

    camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                             read_only=False)
    logger.debug(f"Camera {camera_id} shared memory re-created in CameraProcess for camera {camera_id}")

    def should_continue():
        return ipc.should_continue and not close_self_flag.value

    # Check for configuration updates
    try:
        cv2_video_capture = create_cv2_video_capture(camera_connection.config)

    except Exception as e:
        logger.exception(f"Failed to create cv2.VideoCapture for camera {camera_id}: {e}")
        camera_connection.status.signal_error()
        ipc.should_continue = False
        close_self_flag.value = True
        raise RuntimeError(f"Could not create cv2.VideoCapture for camera {camera_id}") from e

    camera_connection.status.connected.value = True

    extracted_config:CameraConfig| None = None
    try:
        logger.trace(f"Camera {camera_id} process started")
        extracted_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                   prior_config = extracted_config,
                                                   config=camera_connection.config)
        ipc.set_config_by_id(camera_id=camera_id,
                             camera_config=extracted_config, )
        camera_connection.status.connected.value = True
        logger.info(f"Camera {extracted_config.camera_id} ready!")
        while not ipc.all_ready and should_continue():
            wait_1ms()


        # Trigger listening loop
        while should_continue():
            frame_metadata = create_empty_frame_metadata(config=extracted_config,
                                                         frame_number=orchestrator.camera_frame_counts[camera_id].value + 1)
            camera_connection.status.grabbing_frame.value = True

            while should_continue() and not orchestrator.should_grab_by_id(camera_id=camera_id):
                  wait_10us()

            opencv_get_frame(cap=cv2_video_capture,
                             frame_metadata=frame_metadata,
                             camera_shared_memory=camera_shm,
                             )

            camera_connection.status.frame_count.value += 1
            camera_connection.status.grabbing_frame.value = False
            # Check if the camera config has changed
            if extracted_config != ipc.get_config_by_id(camera_id=camera_id, with_lock=False):
                camera_connection.status.updating.value = True
                extracted_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                           config=deepcopy(ipc.camera_configs[camera_id]))
                ipc.set_config_by_id(camera_id=camera_id,
                                     camera_config=extracted_config, )
                camera_connection.status.updating.value = False
                logger.debug(f"Camera {camera_id} config updated to: {extracted_config}")

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
