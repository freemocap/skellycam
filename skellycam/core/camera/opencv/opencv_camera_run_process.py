import logging
import multiprocessing

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.status_models import CameraStatus
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.shared_memory.frame_payload_shared_memory_ring_buffer import \
    FramePayloadSharedMemoryRingBufferDTO, FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_10us, wait_10ms

logger = logging.getLogger(__name__)


def opencv_camera_run_process(camera_id: CameraIdString,
                              config: CameraConfig,
                              ipc: CameraGroupIPC,
                              orchestrator: CameraOrchestrator,
                              camera_shm_dto: FramePayloadSharedMemoryRingBufferDTO,
                              close_self_flag: multiprocessing.Value,
                              ):
    # Configure logging in the child process
    from skellycam.system.logging_configuration.configure_logging import configure_logging
    from skellycam import LOG_LEVEL
    configure_logging(LOG_LEVEL, ws_queue=ipc.pubsub.topics[TopicTypes.LOGS].publication, )
    logger.trace(f"Camera {camera_id} process started")
    self_status: CameraStatus = orchestrator.camera_statuses[camera_id]
    self_status.running.value = True

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

    self_status.connected.value = True

    logger.debug(f"Camera {config.camera_id} connected, re-creating shared memory buffer...")


    camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                             read_only=False)
    logger.success(f"Camera {camera_id} ready!")

    while (not orchestrator.all_cameras_ready or not ipc.recording_manager_ready) and should_continue():
        wait_10ms()

    try:
        logger.debug(f"Camera {config.camera_id} frame grab loop starting...")
        while should_continue():
            frame_metadata = create_empty_frame_metadata(config=config,
                                                         frame_number=orchestrator.camera_frame_counts[camera_id] + 1)
            if ipc.should_pause_flag.value or not config.use_this_camera:
                self_status.is_paused.value = True
                wait_10ms()
                continue

            self_status.is_paused.value = False


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

        logger.debug(f"Camera {config.camera_index} process completed")


