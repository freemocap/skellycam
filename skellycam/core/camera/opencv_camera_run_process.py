import logging
import multiprocessing
from copy import deepcopy

import cv2

from skellycam.core.camera.opencv.apply_config import apply_camera_configuration
from skellycam.core.camera.opencv.create_cv2_video_capture import create_cv2_video_capture
from skellycam.core.camera.opencv.opencv_get_frame import opencv_get_frame
from skellycam.core.camera_group.camera_group_ipc import CameraGroupIPC
from skellycam.core.camera_group.orchestrator.camera_group_orchestrator import CameraGroupOrchestrator
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.shared_memory.frame_payload_shared_memory_ring_buffer import FramePayloadSharedMemoryRingBufferDTO, \
    FramePayloadSharedMemoryRingBuffer
from skellycam.core.types import CameraIdString
from skellycam.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


def opencv_camera_run_process(camera_id: CameraIdString,
                              ipc: CameraGroupIPC,
                              orchestrator: CameraGroupOrchestrator,
                              camera_shm_dto: FramePayloadSharedMemoryRingBufferDTO,
                              close_self_flag: multiprocessing.Value,
                              ws_queue: multiprocessing.Queue,
                              ludacris_speed: bool,
                              ):
    # Configure logging in the child process
    from skellycam.system.logging_configuration.configure_logging import configure_logging
    from skellycam import LOG_LEVEL
    configure_logging(LOG_LEVEL, ws_queue=ws_queue)

    camera_config = deepcopy(ipc.camera_configs[camera_id])
    camera_shm = FramePayloadSharedMemoryRingBuffer.recreate(dto=camera_shm_dto,
                                                             read_only=False)
    logger.debug(f"Camera {camera_id} shared memory re-created in CameraProcess for camera {camera_id}")

    def should_continue():
        return ipc.should_continue and not close_self_flag.value

    # Check for configuration updates

    cv2_video_capture: cv2.VideoCapture | None = None
    try:
        cv2_video_capture = create_cv2_video_capture(camera_config)

        logger.trace(f"Camera {camera_id} process started")
        camera_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                   config=camera_config,
                                                   initial=True)
        ipc.set_config_by_id(camera_id=camera_id,
                             camera_config=camera_config, )

        logger.info(f"Camera {camera_config.camera_id} frame grab trigger loop started!")
        frame_number = -1
        # Trigger listening loop
        while should_continue():

            frame_metadata = create_empty_frame_metadata(config=camera_config,
                                                         frame_number=frame_number + 1)
            while should_continue() and not orchestrator.all_cameras_ready:
                wait_1ms() if not ludacris_speed else None

            if camera_config.principal_camera:
                # If this is the principal camera, we trigger the frame grab
                orchestrator.trigger_frame_grab()
            else:
                # If this is not the principal camera, we need to wait for the orchestrator to trigger the frame grab
                while should_continue() and frame_number < orchestrator.grab_frame_counter:
                    wait_1ms() if not ludacris_speed else None

            frame_number = opencv_get_frame(cap=cv2_video_capture,
                                            frame_metadata=frame_metadata,
                                            camera_shared_memory=camera_shm,
                                            frame_number=frame_number,
                                            )

            if camera_config != ipc.camera_configs[camera_id]:
                # Check if the camera config has changed
                camera_config = apply_camera_configuration(cv2_vid_capture=cv2_video_capture,
                                                           config=deepcopy(ipc.camera_configs[camera_id]),
                                                           initial=False)
                ipc.set_config_by_id(camera_id=camera_id,
                                     camera_config=camera_config, )
                logger.debug(f"Camera {camera_id} config updated to: {camera_config}")
            orchestrator.camera_ready_flags[camera_id].value = True

    except Exception as e:
        logger.exception(f"Exception occurred when running Camera Process for Camera: {camera_id} - {e}")
        raise
    finally:
        logger.debug(f"Releasing camera {camera_id} `cv2.VideoCapture` and shutting down CameraProcess")
        close_self_flag.value = True
        if cv2_video_capture:
            cv2_video_capture.release()
        camera_shm.close()

        logger.debug(f"Camera {camera_config.camera_index} process completed")
