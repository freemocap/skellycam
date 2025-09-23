import logging

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.opencv.opencv_camera_loop import run_opencv_camera_loop
from skellycam.core.camera.opencv.opencv_helpers.setup_opencv_camera_loop import setup_opencv_camera_loop
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.camera_orchestrator import CameraOrchestrator, CameraStatus
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import \
    CameraSharedMemoryRingBuffer
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue, WorkerStrategy

logger = logging.getLogger(__name__)


def opencv_camera_worker_method(camera_id: CameraIdString,
                                config: CameraConfig,
                                ipc: CameraGroupIPC,
                                update_camera_settings_subscription: TopicSubscriptionQueue,
                                shm_subscription: TopicSubscriptionQueue,
                                recording_info_subscription: TopicSubscriptionQueue,
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
    camera_shm: CameraSharedMemoryRingBuffer | None = None

    (camera_shm,
     config,
     cv2_video_capture,
     frame_rec_array) = setup_opencv_camera_loop(camera_shm=camera_shm,
                                                 config=config,
                                                 ipc=ipc,
                                                 self_status=self_status,
                                                 shm_subscription=shm_subscription)

    try:
        logger.debug(f"Camera {config.camera_id} frame grab loop starting...")
        run_opencv_camera_loop(camera_shm=camera_shm,
                               config=config,
                               cv2_video_capture=cv2_video_capture,
                               frame_rec_array=frame_rec_array,
                               ipc=ipc,
                               orchestrator=orchestrator,
                               self_status=self_status,
                               update_camera_settings_subscription=update_camera_settings_subscription,
                               recording_info_subscription=recording_info_subscription)



    except Exception as e:
        self_status.signal_error()
        logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
        ipc.kill_everything()
        raise
    finally:
        logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
        self_status.signal_closing()
        ipc.should_continue = False
        if cv2_video_capture:
            cv2_video_capture.release()
        camera_shm.close()
        self_status.closed.value = True

        logger.debug(f"Camera {config.camera_index} process completed")


