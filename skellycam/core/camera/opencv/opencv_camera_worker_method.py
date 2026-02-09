import logging

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_camera_loop import run_opencv_camera_loop
from skellycam.core.camera.opencv.opencv_helpers.setup_opencv_camera_loop import setup_opencv_camera_loop
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator
from skellycam.core.camera_group.camera_status import CameraStatus
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue

logger = logging.getLogger(__name__)


def opencv_camera_worker_method(
    camera_id: CameraIdString,
    config: CameraConfig,
    ipc: CameraGroupIPC,
    orchestrator: CameraOrchestrator,
    update_camera_settings_subscription: TopicSubscriptionQueue,
    shm_subscription: TopicSubscriptionQueue,
    recording_info_subscription: TopicSubscriptionQueue,
) -> None:
    # NOTE: Logging (including ws_queue forwarding) is now configured
    # automatically by ManagedProcess.run() before this function is called.

    logger.trace(f"Camera {camera_id} worker started")
    self_status: CameraStatus = orchestrator.camera_statuses[camera_id]
    camera_shm: CameraSharedMemoryRingBuffer | None = None

    (camera_shm,
     config,
     cv2_video_capture,
     frame_rec_array) = setup_opencv_camera_loop(
        camera_shm=camera_shm,
        config=config,
        ipc=ipc,
        orchestrator=orchestrator,
        self_status=self_status,
        shm_subscription=shm_subscription,
    )

    try:
        logger.debug(f"Camera {config.camera_id} frame grab loop starting...")
        run_opencv_camera_loop(
            camera_shm=camera_shm,
            config=config,
            cv2_video_capture=cv2_video_capture,
            frame_rec_array=frame_rec_array,
            ipc=ipc,
            orchestrator=orchestrator,
            self_status=self_status,
            update_camera_settings_subscription=update_camera_settings_subscription,
            recording_info_subscription=recording_info_subscription,
        )

    except Exception as e:
        self_status.signal_error()
        logger.exception(
            f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}"
        )
        ipc.kill_everything()
        raise
    finally:
        logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
        self_status.signal_closing()
        ipc.should_continue = False
        if cv2_video_capture:
            cv2_video_capture.release()
        if camera_shm:
            logger.trace(f"Closing camera {config.camera_index} shared memory")
            camera_shm.close()  # close, don't unlink - parent will unlink
        self_status.closed.value = True
        logger.debug(f"Camera {config.camera_index} process completed")